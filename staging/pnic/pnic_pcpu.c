// SPDX-License-Identifier: MIT
// staging/pnic/pnic_pcpu.c
// Fake pNIC + pCPU harness using shared-memory SPSC rings over a hugepage blob.
// - Producer (pNIC) fills rings with descriptor frames referencing the blob
// - Consumers (pCPU threads) pop frames and apply bytewise ops via pfs_pcpu_apply
//
// This is a near-production staging tool: no kernel device, no NIC required.
// Use it to get realistic end-to-end throughput numbers for our local fast path.

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <sched.h>
#include <stdatomic.h>
#include <sys/stat.h>

#include "../../src/packetfs/memory/pfs_hugeblob.h"
#include "../../src/packetfs/ring/pfs_shm_ring.h"
#include "../../src/packetfs/pcpu/pfs_pcpu.h"
#include "../../src/packetfs/gram/pfs_gram.h"

#ifndef likely
#define likely(x)   __builtin_expect(!!(x),1)
#endif
#ifndef unlikely
#define unlikely(x) __builtin_expect(!!(x),0)
#endif

static inline uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }
static inline double now_s(void){ return (double)now_ns() / 1e9; }
static inline uint64_t xorshift64(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }
static void pin_cpu(int cpu){ if(cpu<0) return; cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu,&set); sched_setaffinity(0,sizeof(set),&set); }

typedef struct {
    // topology
    uint32_t ports;           // logical ports
    uint32_t queues;          // queues per port
    uint32_t ring_pow2;       // ring size per queue = 2^ring_pow2
    uint32_t dpf;             // descriptors per frame
    uint32_t align;           // offset/len alignment
    // workload
    uint32_t seg_len;         // if nonzero and mode_contig, fixed segment length
    int mode_contig;          // 1: contiguous spans; 0: pseudo-random scatter
    double duration_s;        // total run time
    // pacing
    double pps;               // frames per second (per producer thread)
    uint32_t burst;           // max burst tokens
    // blob
    size_t blob_bytes;        // backing blob size
    const char* huge_dir;     // hugepage mount (e.g., /mnt/huge1G or /dev/hugepages)
    const char* blob_name;    // file name for blob
    // pCPU program
    int pcpu_enable;          // 1: apply ops; 0: just touch bytes
    pfs_pcpu_op_t prog_ops[16];
    uint8_t prog_imms[16];
    size_t prog_n;
    pfs_pcpu_op_t single_op;  // fallback single op
    uint8_t single_imm;
    // threading
    uint32_t nic_threads;     // producer threads
    uint32_t pcpu_threads;    // consumer threads
    int pin_first_cpu;        // first CPU to pin workers to (round-robin)
    // nic-like extras
    int cq_enable;            // 1: enable completion rings
    const char* metrics_path; // JSONL metrics path
} Cfg;

typedef struct {
    // resources
    PfsHugeBlob blob;
    PfsSpscRing* rings;     // [rings_n]
    PfsSpscRing* cqs;       // [rings_n] completion rings (optional)
    uint32_t    rings_n;
    uint32_t    ring_sz;    // entries per ring
    // frame store
    PfsGramDesc* frames;    // frames[rings_n * ring_sz * dpf]
    uint64_t*    frame_eff; // effective bytes per frame slot (size = rings_n * ring_sz)
    atomic_uint* prod_idx;  // per-ring producer cursor
    // contig state per ring
    uint64_t* contig_off;   // tracked by producers
    // live cfg
    Cfg cfg;
    // stats
    _Atomic uint64_t frames_prod;
    _Atomic uint64_t frames_cons;
    _Atomic uint64_t bytes_eff;
    _Atomic uint64_t cq_push;
    _Atomic uint64_t cq_drop;
    _Atomic int stop;
} Ctx;

static int parse_prog(const char* s, pfs_pcpu_op_t* ops, uint8_t* imms, size_t max){
    if(!s || !*s) return 0;
    char* dup = strdup(s); if(!dup) return 0;
    size_t n=0; char *save=NULL; char* tok=strtok_r(dup, ",", &save);
    while(tok && n<max){
        char* name=tok; char* colon=strchr(tok, ':'); unsigned long v=0;
        if(colon){ *colon='\0'; v=strtoul(colon+1,NULL,0); }
        pfs_pcpu_op_t op=PFS_PCPU_OP_XOR_IMM8; uint8_t iv=(uint8_t)v;
        if(!strcmp(name,"fnv")||!strcmp(name,"fnv64")) { op=PFS_PCPU_OP_CHECKSUM_FNV64; iv=0; }
        else if(!strcmp(name,"crc32c")) { op=PFS_PCPU_OP_CHECKSUM_CRC32C; iv=0; }
        else if(!strcmp(name,"xor")) { op=PFS_PCPU_OP_XOR_IMM8; }
        else if(!strcmp(name,"add")) { op=PFS_PCPU_OP_ADD_IMM8; }
        else if(!strcmp(name,"counteq")) { op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
        else { tok=strtok_r(NULL, ",", &save); continue; }
        ops[n]=op; imms[n]=iv; n++; tok=strtok_r(NULL, ",", &save);
    }
    free(dup); return (int)n;
}

static void init_ctx(Ctx* c, const Cfg* cfg){
    memset(c,0,sizeof(*c)); c->cfg = *cfg;
    c->rings_n = cfg->ports * cfg->queues; if(c->rings_n==0) c->rings_n=1;
    c->ring_sz = 1u << cfg->ring_pow2;
    c->rings = (PfsSpscRing*)calloc(c->rings_n, sizeof(PfsSpscRing));
    for(uint32_t r=0;r<c->rings_n;r++){ if(pfs_spsc_create(&c->rings[r], c->ring_sz)!=0){ fprintf(stderr,"ring create failed: %s\n", strerror(errno)); exit(2);} }
    if(cfg->cq_enable){
        c->cqs = (PfsSpscRing*)calloc(c->rings_n, sizeof(PfsSpscRing));
        for(uint32_t r=0;r<c->rings_n;r++){ if(pfs_spsc_create(&c->cqs[r], c->ring_sz)!=0){ fprintf(stderr,"cq create failed: %s\n", strerror(errno)); exit(2);} }
    }
    size_t frames_n = (size_t)c->rings_n * c->ring_sz * cfg->dpf;
    c->frames = (PfsGramDesc*)calloc(frames_n, sizeof(PfsGramDesc));
    c->frame_eff = (uint64_t*)calloc((size_t)c->rings_n * c->ring_sz, sizeof(uint64_t));
    c->prod_idx = (atomic_uint*)calloc(c->rings_n, sizeof(atomic_uint));
    c->contig_off = (uint64_t*)calloc(c->rings_n, sizeof(uint64_t));
}

static void destroy_ctx(Ctx* c){
    if(!c) return;
    for(uint32_t r=0;r<c->rings_n;r++){ pfs_spsc_destroy(&c->rings[r]); }
    if(c->cqs){ for(uint32_t r=0;r<c->rings_n;r++){ pfs_spsc_destroy(&c->cqs[r]); } }
    free(c->cqs);
    free(c->rings); free(c->frames); free(c->frame_eff); free(c->prod_idx); free(c->contig_off);
    memset(c,0,sizeof(*c));
}

typedef struct { Ctx* ctx; uint32_t ring_first; uint32_t ring_last; int cpu; } ProdArgs;

typedef struct { Ctx* ctx; uint32_t ring_first; uint32_t ring_last; int cpu; } ConsArgs;

static void* producer_fn(void* arg){
    ProdArgs* pa=(ProdArgs*)arg; Ctx* c=pa->ctx; const Cfg* cfg=&c->cfg; if(pa->cpu>=0) pin_cpu(pa->cpu);
    const uint32_t dpf = cfg->dpf; const uint32_t rs=c->ring_sz; const uint32_t rf=pa->ring_first; const uint32_t rl=pa->ring_last; const uint32_t rn = rl>rf? rl-rf : 0;
    uint64_t x = 0x9e3779b97f4a7c15ULL ^ now_ns();
    // simple token bucket pacing per producer
    double tokens = cfg->burst ? (double)cfg->burst : 0.0;
    uint64_t last = now_ns();
    while(!atomic_load_explicit(&c->stop, memory_order_relaxed)){
        // refill tokens
        if(cfg->pps > 0.0){
            uint64_t now = now_ns();
            double dt = (double)(now - last) / 1e9;
            last = now;
            tokens += cfg->pps * dt;
            if(tokens > (double)(cfg->burst ? cfg->burst : (rs))) tokens = (double)(cfg->burst ? cfg->burst : (rs));
        } else {
            tokens = 1.0e9; // effectively unlimited
        }
        for(uint32_t i=0;i<rn;i++){
            if(cfg->pps > 0.0){
                if(tokens < 1.0){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); break; }
                tokens -= 1.0;
            }
            uint32_t r = rf + i; // ring index
            uint32_t idx_local = atomic_fetch_add_explicit(&c->prod_idx[r], 1, memory_order_relaxed) & (rs - 1);
            size_t abs = (size_t)r * rs + idx_local;
            PfsGramDesc* d = &c->frames[abs * dpf];
            uint64_t eff=0;
            if(cfg->mode_contig){
                uint64_t off = c->contig_off[r]; uint64_t seg = cfg->seg_len ? cfg->seg_len : 80u;
                if(cfg->align) seg = (seg + cfg->align - 1) & ~((uint64_t)cfg->align-1ULL);
                for(uint32_t k=0;k<dpf;k++){
                    if(off + seg > c->blob.size) off = (c->blob.size/4) & ~((uint64_t)cfg->align-1ULL);
                    d[k].offset = off; d[k].len = (uint32_t)seg; d[k].flags = 0u; eff += seg; off += seg;
                }
                c->contig_off[r] = off;
            } else {
                for(uint32_t k=0;k<dpf;k++){
                    x = xorshift64(x);
                    uint32_t len = (uint32_t)((x % (cfg->align? (cfg->align*4):4096)) + cfg->align);
                    if(len > 262144u) len = 262144u;
                    uint64_t off = (x % (c->blob.size?c->blob.size:1));
                    if(cfg->align) off &= ~((uint64_t)cfg->align-1ULL);
                    if(off + len > c->blob.size){ if(len > c->blob.size) len = (uint32_t)c->blob.size; off = c->blob.size - len; if(cfg->align) off &= ~((uint64_t)cfg->align-1ULL); }
                    d[k].offset = off; d[k].len = len; d[k].flags = 0u; eff += len;
                }
            }
            c->frame_eff[abs] = eff;
            while(!pfs_spsc_push(&c->rings[r], idx_local)){
                if(atomic_load_explicit(&c->stop, memory_order_relaxed)) break;
            }
            atomic_fetch_add_explicit(&c->frames_prod, 1, memory_order_relaxed);
        }
    }
    return NULL;
}

static void* consumer_fn(void* arg){
    ConsArgs* ca=(ConsArgs*)arg; Ctx* c=ca->ctx; const Cfg* cfg=&c->cfg; if(ca->cpu>=0) pin_cpu(ca->cpu);
    const uint32_t dpf = cfg->dpf; const uint32_t rs=c->ring_sz; const uint32_t rf=ca->ring_first; const uint32_t rl=ca->ring_last; const uint32_t rn = rl>rf? rl-rf : 0;
    uint32_t rr = 0;
    while(!atomic_load_explicit(&c->stop, memory_order_relaxed)){
        uint32_t idx_local; int got=0; size_t abs=0; uint32_t ring_idx=0;
        for(uint32_t t=0;t<rn; ++t){ uint32_t r = rf + ((rr++) % rn); if(pfs_spsc_pop(&c->rings[r], &idx_local)){ abs = (size_t)r * rs + idx_local; ring_idx=r; got=1; break; } }
        if(!got){ struct timespec ts={0, 200000}; nanosleep(&ts,NULL); continue; }
        PfsGramDesc* d = &c->frames[abs * dpf];
        if(cfg->pcpu_enable){
            if(c->cfg.prog_n>0){ for(size_t i=0;i<c->cfg.prog_n;i++){ pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(c->blob.addr, c->blob.size, d, dpf, c->cfg.prog_ops[i], c->cfg.prog_imms[i], 1469598103934665603ULL, &mm); } }
            else { pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); pfs_pcpu_apply(c->blob.addr, c->blob.size, d, dpf, c->cfg.single_op, c->cfg.single_imm, 1469598103934665603ULL, &mm); }
        } else {
            // Touch bytes to simulate processing, without pCPU op cost
            uint64_t eff = c->frame_eff[abs]; (void)eff;
            // Optionally add a very light checksum here if desired
        }
        // completion ring (best-effort)
        if(cfg->cq_enable && c->cqs){ if(!pfs_spsc_push(&c->cqs[ring_idx], idx_local)) { atomic_fetch_add_explicit(&c->cq_drop, 1, memory_order_relaxed); } else { atomic_fetch_add_explicit(&c->cq_push, 1, memory_order_relaxed); } }
        atomic_fetch_add_explicit(&c->bytes_eff, c->frame_eff[abs], memory_order_relaxed);
        atomic_fetch_add_explicit(&c->frames_cons, 1, memory_order_relaxed);
    }
    return NULL;
}

static void usage(const char* argv0){
    fprintf(stderr,
        "Usage: %s [--ports N] [--queues N] [--ring-pow2 P] [--dpf N] [--align N]\n"
        "          [--duration S] [--blob-mb MB] [--huge-dir PATH] [--blob-name NAME]\n"
        "          [--pcpu 0|1] [--op xor|add|crc32c|fnv|counteq] [--imm N] [--prog STR]\n"
        "          [--nic-threads N] [--pcpu-threads N] [--mode contig|scatter] [--seg-len N]\n"
        "          [--pin-first CPU]\n",
        argv0);
}

int main(int argc, char** argv){
    Cfg cfg = {
        .ports=1, .queues=2, .ring_pow2=16, .dpf=64, .align=64,
        .seg_len=256, .mode_contig=0, .duration_s=5.0,
        .pps=0.0, .burst=0,
        .blob_bytes=(size_t)1<<30, .huge_dir="/mnt/huge1G", .blob_name="pnic_blob",
        .pcpu_enable=1, .prog_n=0, .single_op=PFS_PCPU_OP_XOR_IMM8, .single_imm=255,
        .nic_threads=1, .pcpu_threads=2, .pin_first_cpu=0,
        .cq_enable=0, .metrics_path="logs/pnic_pcpu_metrics.jsonl"
    };
    const char* prog_s = NULL; const char* op_s = "xor";

    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--ports")&&i+1<argc) cfg.ports=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--queues")&&i+1<argc) cfg.queues=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--ring-pow2")&&i+1<argc) cfg.ring_pow2=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--dpf")&&i+1<argc) cfg.dpf=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--align")&&i+1<argc) cfg.align=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--duration")&&i+1<argc) cfg.duration_s=strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"--pps")&&i+1<argc) cfg.pps=strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"--burst")&&i+1<argc) cfg.burst=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) cfg.blob_bytes=(size_t)strtoull(argv[++i],NULL,10)<<20;
        else if(!strcmp(argv[i],"--huge-dir")&&i+1<argc) cfg.huge_dir=argv[++i];
        else if(!strcmp(argv[i],"--blob-name")&&i+1<argc) cfg.blob_name=argv[++i];
        else if(!strcmp(argv[i],"--pcpu")&&i+1<argc) cfg.pcpu_enable=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--op")&&i+1<argc) op_s=argv[++i];
        else if(!strcmp(argv[i],"--imm")&&i+1<argc) cfg.single_imm=(uint8_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--prog")&&i+1<argc) prog_s=argv[++i];
        else if(!strcmp(argv[i],"--nic-threads")&&i+1<argc) cfg.nic_threads=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pcpu-threads")&&i+1<argc) cfg.pcpu_threads=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--mode")&&i+1<argc){ const char* m=argv[++i]; cfg.mode_contig = (!strcmp(m,"contig")) ? 1 : 0; }
        else if(!strcmp(argv[i],"--seg-len")&&i+1<argc) cfg.seg_len=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pin-first")&&i+1<argc) cfg.pin_first_cpu=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--cq")&&i+1<argc) cfg.cq_enable=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--metrics")&&i+1<argc) cfg.metrics_path=argv[++i];
        else { usage(argv[0]); return 2; }
    }

    if(prog_s){ cfg.prog_n = (size_t)parse_prog(prog_s, cfg.prog_ops, cfg.prog_imms, 16); }
    if(cfg.prog_n==0){
        if(!strcmp(op_s,"xor")) cfg.single_op = PFS_PCPU_OP_XOR_IMM8;
        else if(!strcmp(op_s,"add")) cfg.single_op = PFS_PCPU_OP_ADD_IMM8;
        else if(!strcmp(op_s,"crc32c")) cfg.single_op = PFS_PCPU_OP_CHECKSUM_CRC32C;
        else if(!strcmp(op_s,"fnv")) cfg.single_op = PFS_PCPU_OP_CHECKSUM_FNV64;
        else if(!strcmp(op_s,"counteq")) cfg.single_op = PFS_PCPU_OP_COUNT_EQ_IMM8;
        else cfg.single_op = PFS_PCPU_OP_XOR_IMM8;
    }

    // Map huge blob
    Ctx ctx; init_ctx(&ctx, &cfg);
    if(pfs_hugeblob_map(cfg.blob_bytes, cfg.huge_dir, cfg.blob_name, &ctx.blob)!=0){ fprintf(stderr,"map hugeblob failed (dir=%s)\n", cfg.huge_dir); destroy_ctx(&ctx); return 1; }
    pfs_hugeblob_set_keep(&ctx.blob, 1);

    // Initialize contig offsets aligned near middle for wrap safety
    for(uint32_t r=0;r<ctx.rings_n;r++){ uint64_t base = ctx.blob.size/4; if(cfg.align) base &= ~((uint64_t)cfg.align-1ULL); ctx.contig_off[r] = base; }

    // Launch threads
    uint32_t nic_threads = cfg.nic_threads? cfg.nic_threads : 1;
    uint32_t pcpu_threads = cfg.pcpu_threads? cfg.pcpu_threads : 1;
    pthread_t *pt = (pthread_t*)calloc(nic_threads, sizeof(pthread_t));
    pthread_t *ct = (pthread_t*)calloc(pcpu_threads, sizeof(pthread_t));

    // Partition rings evenly among nic_threads and pcpu_threads
    uint32_t rings_per_nt = (ctx.rings_n + nic_threads - 1)/nic_threads;
    uint32_t rings_per_ct = (ctx.rings_n + pcpu_threads - 1)/pcpu_threads;

    for(uint32_t i=0;i<nic_threads;i++){
        ProdArgs *pa = (ProdArgs*)calloc(1,sizeof(ProdArgs)); pa->ctx=&ctx; pa->ring_first = i * rings_per_nt; pa->ring_last = (pa->ring_first + rings_per_nt); if(pa->ring_first >= ctx.rings_n) { pa->ring_first=pa->ring_last=ctx.rings_n; }
        if(pa->ring_last > ctx.rings_n) pa->ring_last = ctx.rings_n; pa->cpu = cfg.pin_first_cpu + (int)i;
        pthread_create(&pt[i], NULL, producer_fn, pa);
    }
    for(uint32_t i=0;i<pcpu_threads;i++){
        ConsArgs *ca = (ConsArgs*)calloc(1,sizeof(ConsArgs)); ca->ctx=&ctx; ca->ring_first = i * rings_per_ct; ca->ring_last = (ca->ring_first + rings_per_ct); if(ca->ring_first >= ctx.rings_n) { ca->ring_first=ca->ring_last=ctx.rings_n; }
        if(ca->ring_last > ctx.rings_n) ca->ring_last = ctx.rings_n; ca->cpu = cfg.pin_first_cpu + (int)(nic_threads + i);
        pthread_create(&ct[i], NULL, consumer_fn, ca);
    }

    // Ensure logs directory exists if metrics enabled
    if(cfg.metrics_path && *cfg.metrics_path){ mkdir("logs", 0755); }

    // Periodic stats
    double t0 = now_s(); double next = t0 + 0.5; double tend = t0 + cfg.duration_s; uint64_t last_bytes=0, last_frames=0, last_cqp=0, last_cqd=0;
    while(now_s() < tend){
        struct timespec ts={0, 200000000L}; nanosleep(&ts,NULL);
        double t=now_s(); if(t < next) continue; next += 0.5;
        uint64_t b = atomic_load_explicit(&ctx.bytes_eff, memory_order_relaxed);
        uint64_t f = atomic_load_explicit(&ctx.frames_cons, memory_order_relaxed);
        uint64_t cqp = atomic_load_explicit(&ctx.cq_push, memory_order_relaxed);
        uint64_t cqd = atomic_load_explicit(&ctx.cq_drop, memory_order_relaxed);
        double dt = 0.5; double mbps = ((double)(b - last_bytes)/1e6) / dt; double fps = ((double)(f - last_frames)/dt);
        fprintf(stdout, "[pnic/pcpu] bytes=%.1f MB (%.1f MB/s) frames=%llu (%.0f/s) cq={push=%llu,drop=%llu} rings=%u x %u dpf=%u op=%s%s\n",
            (double)b/1e6, mbps, (unsigned long long)f, fps, (unsigned long long)(cqp), (unsigned long long)(cqd),
            cfg.ports, cfg.queues, cfg.dpf,
            (cfg.prog_n? "prog" : (cfg.single_op==PFS_PCPU_OP_XOR_IMM8? "xor": cfg.single_op==PFS_PCPU_OP_ADD_IMM8? "add": cfg.single_op==PFS_PCPU_OP_CHECKSUM_CRC32C? "crc32c": cfg.single_op==PFS_PCPU_OP_CHECKSUM_FNV64? "fnv": "counteq")),
            (cfg.prog_n? "": ""));
        if(cfg.metrics_path && *cfg.metrics_path){
            FILE* fp=fopen(cfg.metrics_path, "a"); if(fp){
                fprintf(fp, "{\"ts\":%.3f,\"secs\":%.3f,\"bytes\":%llu,\"mbps\":%.1f,\"frames\":%llu,\"fps\":%.0f,\"cq_push\":%llu,\"cq_drop\":%llu}\n",
                    t, t - t0, (unsigned long long)b, mbps, (unsigned long long)f, fps, (unsigned long long)cqp, (unsigned long long)cqd);
                fclose(fp);
            }
        }
        last_bytes=b; last_frames=f; last_cqp=cqp; last_cqd=cqd;
    }

    atomic_store_explicit(&ctx.stop, 1, memory_order_relaxed);
    for(uint32_t i=0;i<nic_threads;i++){ pthread_join(pt[i], NULL); }
    for(uint32_t i=0;i<pcpu_threads;i++){ pthread_join(ct[i], NULL); }
    free(pt); free(ct);

    // Final report
    double secs = now_s() - t0; if(secs <= 0.0) secs = cfg.duration_s;
    uint64_t b = atomic_load_explicit(&ctx.bytes_eff, memory_order_relaxed);
    double avg = (double)b/1e6 / secs;
    fprintf(stdout, "[pnic/pcpu DONE] bytes=%.1f MB secs=%.3f avg=%.1f MB/s\n", (double)b/1e6, secs, avg);

    pfs_hugeblob_unmap(&ctx.blob); destroy_ctx(&ctx);
    return 0;
}
