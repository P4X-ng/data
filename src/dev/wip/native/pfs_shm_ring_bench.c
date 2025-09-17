#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#include "../../realsrc/packetfs/memory/pfs_hugeblob.h"
#include "../../realsrc/packetfs/ring/pfs_shm_ring.h"
#include "../../realsrc/packetfs/pcpu/pfs_pcpu.h"
#include "../../realsrc/packetfs/gram/pfs_gram.h"

// Varint (LEB128) and ZigZag helpers for compact streaming
static inline uint64_t zz_enc64(int64_t v){ return ((uint64_t)v << 1) ^ (uint64_t)(v >> 63); }
static inline int64_t zz_dec64(uint64_t u){ return (int64_t)((u >> 1) ^ (~(u & 1) + 1)); }
static inline size_t uvarint_enc(uint64_t v, uint8_t* out){ size_t i=0; while(v >= 0x80){ out[i++] = (uint8_t)(v | 0x80); v >>= 7; } out[i++] = (uint8_t)v; return i; }
static inline size_t uvarint_dec(const uint8_t* in, size_t max, uint64_t* out){ uint64_t v=0; int shift=0; size_t i=0; while(i<max){ uint8_t b=in[i++]; v |= ((uint64_t)(b & 0x7F)) << shift; if(!(b & 0x80)){ *out=v; return i; } shift += 7; if(shift>63) break; } return 0; }
static inline uint64_t fnv1a64_update(uint64_t h, const void* data, size_t n){ const uint8_t* p=(const uint8_t*)data; for(size_t i=0;i<n;i++){ h ^= p[i]; h *= 1099511628211ULL; } return h; }

// Descriptors come from realsrc/packetfs/gram/pfs_gram.h (PfsGramDesc)

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec + ts.tv_nsec/1e9; }

typedef struct {
    size_t blob_size;
    const char* huge_dir;
    const char* blob_name;
    uint64_t seed;
    uint32_t dpf;          // descriptors per frame (target window)
    uint32_t ring_pow2;    // ring size per queue = 1<<ring_pow2
    uint32_t align;        // descriptor offset/len alignment
    uint32_t payload_max;  // max bytes per payload (for varint streaming), excluding trailing hash
    double duration_s;     // run time
    int threads;           // 1=single-thread loopback; 2=SPSC producer+consumer
    int pcpu_threads;      // number of consumer threads (when threads==2)
    int arith;             // 1 -> arithmetic mode (base + deltas)
    int vstream;           // 1 -> varint streaming mode (no per-frame header), payload ends with 8-byte FNV64
    int verbose;
    // topology
    int ports;             // logical ports
    int queues;            // queues per port
    // pCPU controls
    int pcpu_enable;
    pfs_pcpu_op_t pcpu_op;
    uint8_t pcpu_imm;
    const char* prog;      // optional program string, e.g., "counteq:0,crc32c"
    // Workload shaping
    int mode_contig;       // 1=contiguous segment generation (fixed-desc path)
    uint32_t seg_len;      // segment length (bytes) for contig mode
    uint32_t coalesce_gap; // merge adjacent segments within this gap (bytes)
    int reuse_frames;      // 1=prebuild frames and reuse indices only
    int prefetch_dist;     // prefetch distance (descriptors ahead) in consumer
} BenchCfg;

typedef struct {
    PfsHugeBlob blob;
    // Multi-ring topology
    PfsSpscRing* rings;     // array [rings_n]
    uint32_t ring_sz;       // entries per ring (power of two)
    uint32_t rings_n;       // ports * queues
    // Fixed-desc path buffers
    PfsGramDesc* frames;     // frames[rings_n * ring_sz * dpf]
    uint64_t* frame_eff;     // effective bytes per frame slot (size = rings_n * ring_sz)
    // Varint streaming payloads
    uint8_t* payloads;       // (rings_n * ring_sz) * payload_max bytes (contiguous)
    size_t* payload_len;     // per-slot payload lengths (size = rings_n * ring_sz)
    atomic_uint* prod_idx;   // per-ring producer index array (size=rings_n)
    BenchCfg cfg;
    volatile sig_atomic_t stop;
    // pCPU program (optional)
    pfs_pcpu_op_t prog_ops[16];
    uint8_t prog_imm[16];
    size_t prog_n;
    // stats
    _Atomic uint64_t frames_prod __attribute__((aligned(64)));
    _Atomic uint64_t frames_cons __attribute__((aligned(64)));
    _Atomic uint64_t bytes_eff __attribute__((aligned(64)));
    // contig state per ring
    uint64_t* contig_off;  // next offset per ring
} BenchCtx;

typedef struct {
    BenchCtx* ctx;
    uint32_t ring_start;  // inclusive
    uint32_t ring_end;    // exclusive
} ConsumerArgs;

static inline uint64_t xorshift64(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }

static void* producer_thread(void* arg){
    BenchCtx* ctx = (BenchCtx*)arg; const BenchCfg* c = &ctx->cfg; const uint32_t dpf = c->dpf; const uint32_t rs = ctx->ring_sz; const uint32_t rn = ctx->rings_n; uint32_t rr = 0;
    uint64_t x = ctx->cfg.seed ? ctx->cfg.seed : 0x12345678ULL;
    const uint64_t base = ctx->blob.size / 2;
    while(!ctx->stop){
        // choose ring and reserve next frame slot index
        uint32_t r = rr++ % rn;
        uint32_t idx_local = atomic_fetch_add_explicit(&ctx->prod_idx[r], 1, memory_order_relaxed) & (rs - 1);
        size_t abs = (size_t)r * rs + idx_local;
        uint64_t eff=0;
        uint64_t prev_off = 0;
        if(ctx->cfg.mode_contig && !ctx->cfg.arith){
            // Fixed-desc contiguous mode (on-the-fly)
            PfsGramDesc* d = &ctx->frames[abs * dpf];
            uint64_t eff=0; uint64_t off = ctx->contig_off[r];
            for(uint32_t i=0;i<dpf;i++){
                uint64_t seg = c->seg_len ? c->seg_len : 80;
                if(c->align) seg = (seg + c->align - 1) & ~((uint64_t)c->align-1ULL);
                if(off + seg > ctx->blob.size){ off = (ctx->blob.size/4) & ~((uint64_t)c->align-1ULL); }
                d[i].offset = off; d[i].len = (uint32_t)seg; d[i].flags = 0u;
                eff += seg; off += seg;
            }
            ctx->contig_off[r] = off;
            ctx->frame_eff[abs] = eff;
        }
        else if(ctx->cfg.arith && ctx->cfg.vstream){
            // Build varint payload: [delta varint][len varint]... then 8-byte FNV64 of referenced bytes
            uint8_t* p = ctx->payloads + abs * ctx->cfg.payload_max;
            size_t pos = 0; uint32_t wrote = 0;
            // Temp store of generated pairs to compute hash
            // (we can recompute while hashing to avoid storing all pairs; do inline)
            for(uint32_t i=0;i<dpf;i++){
                x = xorshift64(x);
                uint32_t len = (uint32_t)((x % (ctx->cfg.align? (ctx->cfg.align*4):4096)) + ctx->cfg.align);
                if(len > 262144u) len = 262144u;
                uint64_t off = (x % (ctx->blob.size?ctx->blob.size:1));
                if(ctx->cfg.align) off &= ~((uint64_t)ctx->cfg.align-1ULL);
                if(off + len > ctx->blob.size){ if(len > ctx->blob.size) len = (uint32_t)ctx->blob.size; off = ctx->blob.size - len; if(ctx->cfg.align) off &= ~((uint64_t)ctx->cfg.align-1ULL); }
                int64_t delta = (i==0) ? (int64_t)(off - base) : (int64_t)(off - prev_off);
                uint8_t tmp[16]; size_t n1 = uvarint_enc(zz_enc64(delta), tmp);
                uint8_t tmp2[16]; size_t n2 = uvarint_enc((uint64_t)len, tmp2);
                if(pos + n1 + n2 + 8 > ctx->cfg.payload_max){ break; }
                memcpy(p+pos, tmp, n1); pos += n1;
                memcpy(p+pos, tmp2, n2); pos += n2;
                prev_off = off; eff += len; wrote++;
            }
            // Compute FNV64 over referenced bytes
            uint64_t h = 1469598103934665603ULL; size_t rpos = 0; uint64_t off_acc = base;
            for(uint32_t i=0;i<wrote;i++){
                uint64_t u; size_t m = uvarint_dec(p+rpos, pos-rpos, &u); rpos += m; int64_t delta = zz_dec64(u);
                uint64_t l; size_t m2 = uvarint_dec(p+rpos, pos-rpos, &l); rpos += m2;
                off_acc = (i==0) ? (base + (int64_t)delta) : (off_acc + (int64_t)delta);
                if(off_acc + l <= ctx->blob.size){ h = fnv1a64_update(h, (uint8_t*)ctx->blob.addr + off_acc, (size_t)l); }
            }
            // Append hash
            if(pos + 8 <= ctx->cfg.payload_max){ memcpy(p+pos, &h, 8); pos += 8; }
            ctx->payload_len[abs] = pos;
            ctx->frame_eff[abs] = eff;
        } else {
            // Fixed-desc path
            PfsGramDesc* d = &ctx->frames[abs * dpf];
            for(uint32_t i=0;i<dpf;i++){
                x = xorshift64(x);
                uint32_t len = (uint32_t)((x % (ctx->cfg.align? (ctx->cfg.align*4):4096)) + ctx->cfg.align);
                if(len > 262144u) len = 262144u;
                uint64_t off = (x % (ctx->blob.size?ctx->blob.size:1));
                if(ctx->cfg.align) off &= ~((uint64_t)ctx->cfg.align-1ULL);
                if(off + len > ctx->blob.size){ if(len > ctx->blob.size) len = (uint32_t)ctx->blob.size; off = ctx->blob.size - len; if(ctx->cfg.align) off &= ~((uint64_t)ctx->cfg.align-1ULL); }
                if(ctx->cfg.arith){ if(i==0){ d[i].offset = off - base; } else { d[i].offset = off - prev_off; } prev_off = off; }
                else { d[i].offset = off; }
                d[i].len = len; d[i].flags = ctx->cfg.arith ? 1u : 0u; eff += len;
            }
            ctx->frame_eff[abs] = eff;
        }
        // push to ring (spin until space)
        while(!pfs_spsc_push(&ctx->rings[r], idx_local)){
            if(ctx->stop) break; // backoff
        }
        atomic_fetch_add_explicit(&ctx->frames_prod, 1, memory_order_relaxed);
    }
    return NULL;
}


static void* consumer_thread(void* arg){
    BenchCtx* ctx = (BenchCtx*)arg; const BenchCfg* c = &ctx->cfg; const uint32_t dpf = c->dpf; const uint32_t rs = ctx->ring_sz; const uint32_t rn = ctx->rings_n; uint32_t rr = 0;
    uint64_t csum=1469598103934665603ULL;
    while(!ctx->stop){
        // round-robin across rings
        uint32_t idx_local; int got=0; size_t abs=0; uint32_t tries=0;
        for(tries=0; tries<rn; ++tries){
            uint32_t r = (rr++) % rn;
            if(pfs_spsc_pop(&ctx->rings[r], &idx_local)){
                abs = (size_t)r * rs + idx_local; got=1; break;
            }
        }
        if(!got){ struct timespec ts={0, 200000}; nanosleep(&ts,NULL); continue; }
        if(ctx->cfg.arith && ctx->cfg.vstream){
            // Parse varint payload, build descs optionally, apply pCPU, and touch bytes
            uint8_t* p = ctx->payloads + abs * ctx->cfg.payload_max;
            size_t plen = ctx->payload_len[abs];
            if(plen >= 8){
                uint64_t want_hash; memcpy(&want_hash, p + plen - 8, 8);
                size_t pos = 0; uint64_t base = ctx->blob.size / 2; uint64_t off_acc = base; uint64_t h = 1469598103934665603ULL; uint64_t eff=0;
                PfsGramDesc descs[1024]; size_t dcnt=0;
                while(pos + 8 <= plen){
                    uint64_t u; size_t m = uvarint_dec(p+pos, plen - 8 - pos, &u); if(!m) break; pos += m;
                    uint64_t l; size_t m2 = uvarint_dec(p+pos, plen - 8 - pos, &l); if(!m2) break; pos += m2;
                    int64_t delta = zz_dec64(u);
                    off_acc = (pos == (size_t)(m + m2)) ? (base + delta) : (off_acc + delta);
                    if(off_acc + l <= ctx->blob.size){ h = fnv1a64_update(h, (uint8_t*)ctx->blob.addr + off_acc, (size_t)l); eff += l; if(c->pcpu_enable && dcnt<1024){ descs[dcnt].offset=off_acc; descs[dcnt].len=(uint32_t)l; descs[dcnt].flags=0; dcnt++; } }
                }
if(c->pcpu_enable && dcnt){
    if(ctx->prog_n>0){ pfs_pcpu_metrics_t mm; for(size_t i=0;i<ctx->prog_n;i++){ memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)descs, dcnt, ctx->prog_ops[i], ctx->prog_imm[i], 1469598103934665603ULL, &mm); } }
    else { pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); (void)pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)descs, dcnt, c->pcpu_op, c->pcpu_imm, 1469598103934665603ULL, &mm); }
}
                (void)want_hash; // we could compare h==want_hash and log
                atomic_fetch_add_explicit(&ctx->bytes_eff, eff, memory_order_relaxed);
            }
            atomic_fetch_add_explicit(&ctx->frames_cons, 1, memory_order_relaxed);
        } else {
            PfsGramDesc* d = &ctx->frames[abs * dpf];
            uint64_t base = ctx->blob.size / 2;
            uint64_t off_accum = base;
if(c->pcpu_enable){ if(ctx->prog_n>0){ pfs_pcpu_metrics_t mm; for(size_t i=0;i<ctx->prog_n;i++){ memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)d, dpf, ctx->prog_ops[i], ctx->prog_imm[i], 1469598103934665603ULL, &mm); } } else { pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); (void)pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)d, dpf, c->pcpu_op, c->pcpu_imm, 1469598103934665603ULL, &mm); } }
            for(uint32_t i=0;i<dpf;i++){
                uint64_t off = d[i].offset; uint32_t len = d[i].len;
                if(d[i].flags & 1u){ if(i==0){ off = base + off; off_accum = off; } else { off_accum += off; off = off_accum; } }
                if(off+len <= ctx->blob.size){ csum = fnv1a64_update(csum, (uint8_t*)ctx->blob.addr + off, len); }
            }
            atomic_fetch_add_explicit(&ctx->bytes_eff, ctx->frame_eff[abs], memory_order_relaxed);
            atomic_fetch_add_explicit(&ctx->frames_cons, 1, memory_order_relaxed);
        }
    }
    return NULL;
}

// Consumer over a subset of rings [ring_start, ring_end)
static void* consumer_thread_range(void* arg){
    ConsumerArgs* ca = (ConsumerArgs*)arg;
    BenchCtx* ctx = ca->ctx; const BenchCfg* c = &ctx->cfg; const uint32_t dpf = c->dpf; const uint32_t rs = ctx->ring_sz;
    const uint32_t r_begin = ca->ring_start; const uint32_t r_end = ca->ring_end;
    const uint32_t rn_local = (r_end > r_begin) ? (r_end - r_begin) : 0;
    if(rn_local == 0) return NULL;
    uint64_t csum=1469598103934665603ULL; uint32_t rr=0;
    while(!ctx->stop){
        uint32_t idx_local; int got=0; size_t abs=0; uint32_t tries=0;
        for(tries=0; tries<rn_local; ++tries){
            uint32_t r = r_begin + ((rr++) % rn_local);
            if(pfs_spsc_pop(&ctx->rings[r], &idx_local)){
                abs = (size_t)r * rs + idx_local; got=1; break;
            }
        }
        if(!got){ struct timespec ts={0, 200000}; nanosleep(&ts,NULL); continue; }
        if(ctx->cfg.arith && ctx->cfg.vstream){
            uint8_t* p = ctx->payloads + abs * ctx->cfg.payload_max;
            size_t plen = ctx->payload_len[abs];
            if(plen >= 8){
                uint64_t want_hash; memcpy(&want_hash, p + plen - 8, 8);
                size_t pos = 0; uint64_t base = ctx->blob.size / 2; uint64_t off_acc = base; uint64_t h = 1469598103934665603ULL; uint64_t eff=0;
                PfsGramDesc descs[1024]; size_t dcnt=0;
                while(pos + 8 <= plen){
                    uint64_t u; size_t m = uvarint_dec(p+pos, plen - 8 - pos, &u); if(!m) break; pos += m;
                    uint64_t l; size_t m2 = uvarint_dec(p+pos, plen - 8 - pos, &l); if(!m2) break; pos += m2;
                    int64_t delta = zz_dec64(u);
                    uint64_t off_acc2 = (pos == (size_t)(m + m2)) ? (base + delta) : (off_acc + delta);
                    off_acc = off_acc2;
                    if(off_acc + l <= ctx->blob.size){ h = fnv1a64_update(h, (uint8_t*)ctx->blob.addr + off_acc, (size_t)l); eff += l; if(c->pcpu_enable && dcnt<1024){ descs[dcnt].offset=off_acc; descs[dcnt].len=(uint32_t)l; descs[dcnt].flags=0; dcnt++; } }
                }
                if(c->pcpu_enable && dcnt){
                    if(ctx->prog_n>0){ pfs_pcpu_metrics_t mm; for(size_t i=0;i<ctx->prog_n;i++){ memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)descs, dcnt, ctx->prog_ops[i], ctx->prog_imm[i], 1469598103934665603ULL, &mm); } }
                    else { pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); (void)pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)descs, dcnt, c->pcpu_op, c->pcpu_imm, 1469598103934665603ULL, &mm); }
                }
                (void)want_hash; // optional compare h==want_hash
                atomic_fetch_add_explicit(&ctx->bytes_eff, eff, memory_order_relaxed);
            }
            atomic_fetch_add_explicit(&ctx->frames_cons, 1, memory_order_relaxed);
        } else {
            PfsGramDesc* d = &ctx->frames[abs * dpf];
            uint64_t base = ctx->blob.size / 2;
            uint64_t off_accum = base;
            if(c->pcpu_enable){ if(ctx->prog_n>0){ pfs_pcpu_metrics_t mm; for(size_t i=0;i<ctx->prog_n;i++){ memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)d, dpf, ctx->prog_ops[i], ctx->prog_imm[i], 1469598103934665603ULL, &mm); } } else { pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); (void)pfs_pcpu_apply(ctx->blob.addr, ctx->blob.size, (const PfsGramDesc*)d, dpf, c->pcpu_op, c->pcpu_imm, 1469598103934665603ULL, &mm); } }
            for(uint32_t i=0;i<dpf;i++){
                uint64_t off = d[i].offset; uint32_t len = d[i].len;
                if(d[i].flags & 1u){ if(i==0){ off = base + off; off_accum = off; } else { off_accum += off; off = off_accum; } }
                if(off+len <= ctx->blob.size){ csum = fnv1a64_update(csum, (uint8_t*)ctx->blob.addr + off, len); }
            }
            atomic_fetch_add_explicit(&ctx->bytes_eff, ctx->frame_eff[abs], memory_order_relaxed);
            atomic_fetch_add_explicit(&ctx->frames_cons, 1, memory_order_relaxed);
        }
    }
    return NULL;
}

static void usage(const char* prog){
    fprintf(stderr,
        "Usage: %s --blob-size BYTES [--huge-dir DIR] [--blob-name NAME]\n"
        "          [--seed S] [--dpf N] [--ring-pow2 P] [--align A] [--duration S] [--threads 1|2] [--pcpu-threads N] [--quiet]\n"
        "          [--pcpu 0|1] [--pcpu-op fnv|crc32c|xor|add|counteq] [--imm N]\n",
        prog);
}

int main(int argc, char** argv){
    signal(SIGINT, on_sigint);
BenchCfg cfg={0}; cfg.blob_size=2ULL<<30; cfg.huge_dir="/dev/hugepages"; cfg.blob_name="pfs_shm_blob"; cfg.seed=0x12345678ULL; cfg.dpf=64; cfg.ring_pow2=16; cfg.align=64; cfg.payload_max=2048; cfg.duration_s=5.0; cfg.threads=2; cfg.pcpu_threads=1; cfg.arith=0; cfg.vstream=1; cfg.verbose=1; cfg.ports=1; cfg.queues=1; cfg.pcpu_enable=0; cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_FNV64; cfg.pcpu_imm=0; cfg.prog=NULL; cfg.mode_contig=0; cfg.seg_len=80; cfg.coalesce_gap=64; cfg.reuse_frames=0; cfg.prefetch_dist=2;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--blob-size") && i+1<argc) cfg.blob_size=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) cfg.huge_dir=argv[++i];
        else if(!strcmp(argv[i],"--blob-name") && i+1<argc) cfg.blob_name=argv[++i];
        else if(!strcmp(argv[i],"--seed") && i+1<argc) cfg.seed=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--dpf") && i+1<argc) cfg.dpf=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--ring-pow2") && i+1<argc) cfg.ring_pow2=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--align") && i+1<argc) cfg.align=(uint32_t)strtoul(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--duration") && i+1<argc) cfg.duration_s=strtod(argv[++i],NULL);
else if(!strcmp(argv[i],"--threads") && i+1<argc) cfg.threads=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pcpu-threads") && i+1<argc) cfg.pcpu_threads=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--arith") && i+1<argc) cfg.arith=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--vstream") && i+1<argc) cfg.vstream=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--payload") && i+1<argc) cfg.payload_max=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--ports") && i+1<argc) cfg.ports=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--queues") && i+1<argc) cfg.queues=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pcpu") && i+1<argc) cfg.pcpu_enable=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pcpu-op") && i+1<argc){ const char* o=argv[++i]; if(!strcmp(o,"fnv")||!strcmp(o,"fnv64")) cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_FNV64; else if(!strcmp(o,"crc32c")) cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_CRC32C; else if(!strcmp(o,"xor")) cfg.pcpu_op=PFS_PCPU_OP_XOR_IMM8; else if(!strcmp(o,"add")) cfg.pcpu_op=PFS_PCPU_OP_ADD_IMM8; else if(!strcmp(o,"counteq")) cfg.pcpu_op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
        else if(!strcmp(argv[i],"--imm") && i+1<argc) cfg.pcpu_imm=(uint8_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--prog") && i+1<argc) cfg.prog=argv[++i];
        else if(!strcmp(argv[i],"--mode") && i+1<argc){ const char* m=argv[++i]; cfg.mode_contig = (!strcmp(m,"contig")) ? 1 : 0; }
        else if(!strcmp(argv[i],"--seg-len") && i+1<argc) cfg.seg_len=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--coalesce-gap") && i+1<argc) cfg.coalesce_gap=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--reuse-frames") && i+1<argc) cfg.reuse_frames=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--prefetch-dist") && i+1<argc) cfg.prefetch_dist=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--quiet")) cfg.verbose=0;
        else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){ usage(argv[0]); return 0; }
    }
if(cfg.verbose) fprintf(stderr,"[SHM] blob=%zu dir=%s name=%s dpf=%u ring=2^%u align=%u payload=%u dur=%.2f threads=%d cthreads=%d arith=%d vstream=%d\n",
            (size_t)cfg.blob_size, cfg.huge_dir, cfg.blob_name, cfg.dpf, cfg.ring_pow2, cfg.align, cfg.payload_max, cfg.duration_s, cfg.threads, cfg.pcpu_threads, cfg.arith, cfg.vstream);

    BenchCtx ctx; memset(&ctx,0,sizeof(ctx)); ctx.cfg=cfg;
    if(pfs_hugeblob_map(cfg.blob_size, cfg.huge_dir, cfg.blob_name, &ctx.blob)!=0){ fprintf(stderr,"map blob: %s\n", strerror(errno)); return 1; }
    pfs_hugeblob_set_keep(&ctx.blob, 1);
    ctx.ring_sz = 1u << cfg.ring_pow2;
    ctx.rings_n = (uint32_t)((cfg.ports>0?cfg.ports:1) * (cfg.queues>0?cfg.queues:1));
    // Create rings and producer indices
    ctx.rings = (PfsSpscRing*)calloc(ctx.rings_n, sizeof(PfsSpscRing));
    if(!ctx.rings){ fprintf(stderr,"alloc rings failed\n"); return 1; }
    for(uint32_t r=0;r<ctx.rings_n;r++){ if(pfs_spsc_create(&ctx.rings[r], ctx.ring_sz)!=0){ fprintf(stderr,"ring create r=%u: %s\n", r, strerror(errno)); return 1; } }
    ctx.prod_idx = (atomic_uint*)calloc(ctx.rings_n, sizeof(atomic_uint)); if(!ctx.prod_idx){ fprintf(stderr,"alloc prod_idx failed\n"); return 1; }

    size_t frames_total = (size_t)ctx.rings_n * ctx.ring_sz * cfg.dpf;
    ctx.frames = (PfsGramDesc*)aligned_alloc(64, frames_total * sizeof(PfsGramDesc));
    if(!ctx.frames){ fprintf(stderr,"alloc frames failed\n"); return 1; }
    ctx.frame_eff = (uint64_t*)aligned_alloc(64, (size_t)ctx.rings_n * ctx.ring_sz * sizeof(uint64_t));
    if(!ctx.frame_eff){ fprintf(stderr,"alloc frame_eff failed\n"); return 1; }
    // Varint streaming buffers (allocate only if used)
    if(cfg.arith && cfg.vstream){
        ctx.payloads = (uint8_t*)aligned_alloc(64, (size_t)ctx.rings_n * ctx.ring_sz * cfg.payload_max);
        if(!ctx.payloads){ fprintf(stderr,"alloc payloads failed\n"); return 1; }
        ctx.payload_len = (size_t*)aligned_alloc(64, (size_t)ctx.rings_n * ctx.ring_sz * sizeof(size_t));
        if(!ctx.payload_len){ fprintf(stderr,"alloc payload_len failed\n"); return 1; }
    } else {
        ctx.payloads = NULL;
        ctx.payload_len = NULL;
    }

    // Contig offsets per ring
    ctx.contig_off = (uint64_t*)calloc(ctx.rings_n, sizeof(uint64_t));
    if(!ctx.contig_off){ fprintf(stderr, "alloc contig_off failed\n"); return 1; }

    // Optionally prebuild frames for contig mode (fixed desc path)
    if(cfg.mode_contig && cfg.reuse_frames && cfg.arith==0){
        for(uint32_t r=0;r<ctx.rings_n;r++){
            uint64_t off = (ctx.blob.size/4) & ~((uint64_t)cfg.align-1ULL);
            for(uint32_t idx_local=0; idx_local<ctx.ring_sz; idx_local++){
                size_t abs = (size_t)r * ctx.ring_sz + idx_local;
                PfsGramDesc* d = &ctx.frames[abs * cfg.dpf];
                uint64_t eff=0; uint64_t prev_off=0; const uint64_t base = ctx.blob.size/2;
                for(uint32_t i=0;i<cfg.dpf;i++){
                    uint64_t seg = cfg.seg_len ? cfg.seg_len : 80;
                    if(cfg.align) seg = (seg + cfg.align - 1) & ~((uint64_t)cfg.align-1ULL);
                    if(off + seg > ctx.blob.size){ off = (ctx.blob.size/4) & ~((uint64_t)cfg.align-1ULL); }
                    d[i].offset = off; d[i].len = (uint32_t)seg; d[i].flags = 0u;
                    eff += seg; off += seg;
                }
                ctx.frame_eff[abs] = eff;
            }
            ctx.contig_off[r] = (ctx.blob.size/4) & ~((uint64_t)cfg.align-1ULL);
        }
    }

    // Parse program if provided
    ctx.prog_n = 0;
    if(cfg.prog && *cfg.prog){
        char* s = strdup(cfg.prog); char* save=NULL; char* tok = strtok_r(s, ",", &save);
        while(tok && ctx.prog_n < 16){
            char* colon = strchr(tok, ':');
            if(colon){ *colon='\0'; const char* name=tok; const char* iv=colon+1; unsigned long v=strtoul(iv,NULL,0);
                if(!strcmp(name,"fnv")||!strcmp(name,"fnv64")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_CHECKSUM_FNV64; ctx.prog_imm[ctx.prog_n]=(uint8_t)v; }
                else if(!strcmp(name,"crc32c")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_CHECKSUM_CRC32C; ctx.prog_imm[ctx.prog_n]=(uint8_t)v; }
                else if(!strcmp(name,"xor")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_XOR_IMM8; ctx.prog_imm[ctx.prog_n]=(uint8_t)v; }
                else if(!strcmp(name,"add")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_ADD_IMM8; ctx.prog_imm[ctx.prog_n]=(uint8_t)v; }
                else if(!strcmp(name,"counteq")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_COUNT_EQ_IMM8; ctx.prog_imm[ctx.prog_n]=(uint8_t)v; }
                else { /* ignore unknown */ tok=strtok_r(NULL, ",", &save); continue; }
                ctx.prog_n++;
            } else {
                const char* name=tok; uint8_t v=0;
                if(!strcmp(name,"fnv")||!strcmp(name,"fnv64")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_CHECKSUM_FNV64; ctx.prog_imm[ctx.prog_n]=v; }
                else if(!strcmp(name,"crc32c")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_CHECKSUM_CRC32C; ctx.prog_imm[ctx.prog_n]=v; }
                else if(!strcmp(name,"xor")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_XOR_IMM8; ctx.prog_imm[ctx.prog_n]=v; }
                else if(!strcmp(name,"add")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_ADD_IMM8; ctx.prog_imm[ctx.prog_n]=v; }
                else if(!strcmp(name,"counteq")) { ctx.prog_ops[ctx.prog_n]=PFS_PCPU_OP_COUNT_EQ_IMM8; ctx.prog_imm[ctx.prog_n]=v; }
                else { tok=strtok_r(NULL, ",", &save); continue; }
                ctx.prog_n++;
            }
            tok = strtok_r(NULL, ",", &save);
        }
        free(s);
    }

    pthread_t prod_tid=0, cons_tid=0;
    double t0 = now_sec(), tlast=t0;

    if(cfg.threads == 1){
        uint64_t x = cfg.seed ? cfg.seed : 0x12345678ULL;
        uint64_t bytes=0; uint64_t frames=0;
        while(!g_stop){
            if(cfg.duration_s>0 && (now_sec()-t0)>=cfg.duration_s) break;
            // produce into next slot modulo total slots
            size_t total_slots = (size_t)((cfg.ports>0?cfg.ports:1) * (cfg.queues>0?cfg.queues:1)) * (size_t)(1u<<cfg.ring_pow2);
            size_t idx = (size_t)(frames % total_slots);
            PfsGramDesc* d = &ctx.frames[idx * cfg.dpf];
            uint64_t eff=0;
uint64_t prev_off=0;
            const uint64_t base = ctx.blob.size / 2;
            for(uint32_t i=0;i<cfg.dpf;i++){
                x = xorshift64(x);
                uint32_t len = (uint32_t)((x % (cfg.align? (cfg.align*4):4096)) + cfg.align);
                if(len > 262144u) len = 262144u;
                uint64_t off = (x % (ctx.blob.size?ctx.blob.size:1));
                if(cfg.align) off &= ~((uint64_t)cfg.align-1ULL);
                if(off + len > ctx.blob.size){ if(len > ctx.blob.size) len = (uint32_t)ctx.blob.size; off = ctx.blob.size - len; if(cfg.align) off &= ~((uint64_t)cfg.align-1ULL); }
                if(cfg.arith){ if(i==0){ d[i].offset = off - base; } else { d[i].offset = off - prev_off; } prev_off = off; }
                else { d[i].offset = off; }
                d[i].len = len; d[i].flags = cfg.arith ? 1u : 0u; eff += len;
            }
            // consume immediately
            uint64_t off_acc=base;
            for(uint32_t i=0;i<cfg.dpf;i++){
                uint64_t off=d[i].offset; uint32_t len=d[i].len;
                if(d[i].flags & 1u){ if(i==0){ off = base + off; off_acc = off; } else { off_acc += off; off = off_acc; } }
                if(off+len <= ctx.blob.size){ (void)fnv1a64_update(1469598103934665603ULL, (uint8_t*)ctx.blob.addr + off, len); }
            }
            bytes += eff; frames++;
            double tn=now_sec(); if(cfg.verbose && (tn - tlast) >= 0.5){ double mb=bytes/1e6; double mbps=mb/(tn-t0); fprintf(stderr,"[SHM] eff=%.1f MB avg=%.1f MB/s frames=%llu\n", mb, mbps, (unsigned long long)frames); tlast=tn; }
        }
        double t1=now_sec(); double mb=bytes/1e6; double mbps=mb/(t1-t0+1e-9);
        fprintf(stderr,"[SHM DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames=%llu\n",
            (unsigned long long)bytes, mb, (t1-t0), mbps, (unsigned long long)frames);
    } else {
        // producer + N consumer threads (SPSC per ring; rings are partitioned among consumers)
        pthread_create(&prod_tid,NULL,producer_thread,&ctx);
        unsigned int consumers = (cfg.pcpu_threads > 0) ? (unsigned int)cfg.pcpu_threads : 1u;
        if(consumers > ctx.rings_n) consumers = ctx.rings_n;
        pthread_t* cons = (pthread_t*)calloc(consumers, sizeof(pthread_t));
        ConsumerArgs* cargs = (ConsumerArgs*)calloc(consumers, sizeof(ConsumerArgs));
        uint32_t base = ctx.rings_n / consumers; uint32_t rem = ctx.rings_n % consumers; uint32_t start = 0;
        for(unsigned int i=0;i<consumers;i++){
            uint32_t cnt = base + (i < rem ? 1u : 0u);
            cargs[i].ctx = &ctx; cargs[i].ring_start = start; cargs[i].ring_end = start + cnt; start += cnt;
            pthread_create(&cons[i], NULL, consumer_thread_range, &cargs[i]);
        }
        while(!g_stop){
            if(cfg.duration_s>0 && (now_sec()-t0)>=cfg.duration_s){ ctx.stop=1; break; }
            double tn=now_sec(); if(cfg.verbose && (tn - tlast) >= 0.5){
                uint64_t b = atomic_load_explicit(&ctx.bytes_eff, memory_order_relaxed);
                uint64_t fc= atomic_load_explicit(&ctx.frames_cons, memory_order_relaxed);
                double mb=b/1e6; double mbps=mb/(tn - t0);
                fprintf(stderr,"[SHM] eff=%.1f MB avg=%.1f MB/s frames=%llu\n", mb, mbps, (unsigned long long)fc);
                tlast=tn;
            }
            struct timespec ts={0, 100000000}; nanosleep(&ts,NULL);
        }
        ctx.stop=1;
        pthread_join(prod_tid,NULL);
        for(unsigned int i=0;i<consumers;i++){ pthread_join(cons[i], NULL); }
        free(cons); free(cargs);
        double t1=now_sec();
        uint64_t b = atomic_load_explicit(&ctx.bytes_eff, memory_order_relaxed);
        uint64_t fp= atomic_load_explicit(&ctx.frames_prod, memory_order_relaxed);
        uint64_t fc= atomic_load_explicit(&ctx.frames_cons, memory_order_relaxed);
        double mb=b/1e6; double mbps=mb/(t1 - t0 + 1e-9);
        fprintf(stderr,"[SHM DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames_prod=%llu frames_cons=%llu\n",
            (unsigned long long)b, mb, (t1-t0), mbps, (unsigned long long)fp, (unsigned long long)fc);
    }

    if(ctx.rings){ for(uint32_t r=0;r<ctx.rings_n;r++){ pfs_spsc_destroy(&ctx.rings[r]); } free(ctx.rings); }
    if(ctx.prod_idx) free(ctx.prod_idx);
    if(ctx.frames) free(ctx.frames); if(ctx.frame_eff) free(ctx.frame_eff);
    if(ctx.payloads) free(ctx.payloads);
    if(ctx.payload_len) free(ctx.payload_len);
    pfs_hugeblob_unmap(&ctx.blob);
    return 0;
}

