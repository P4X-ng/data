#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <net/if.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/poll.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include <xdp/xsk.h>

#include "pfs_stream_afxdp.h"
#include "../memory/pfs_hugeblob.h"
#include "../gram/pfs_gram.h"

#define PFS_MAX_STREAMS 256

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

// Simple descriptor-only frame header for AF_XDP streaming
typedef struct {
    uint32_t magic;     // 'PFSX' 0x50565358
    uint16_t version;   // 1
    uint16_t flags;     // reserved
    uint64_t seq;       // frame sequence
    uint16_t desc_count;// number of PfsGramDesc records following
    uint16_t reserved;
} __attribute__((packed)) PfsXdpFrameHdr;

static void die(const char* fmt, ...){ va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);} 

static inline uint64_t xorshift64(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }

typedef struct {
    const char* ifname;
    uint32_t queue;
    int zerocopy;
    size_t blob_size;
    const char* huge_dir;
    const char* blob_name;
    uint64_t seed;
    uint32_t desc_per_frame;
    uint64_t total_bytes; // 0 -> time-bound
    double duration_s;    // 0 -> byte-bound
    uint32_t align;
    int verbose;
    const char* corr_listen; // host:port for UDP NAKs
    const char* desc_file;   // optional: path to descriptor list (offset,len) per line
    PfsXdpMode mode_req;     // requested XDP mode
    int arith;               // arithmetic mode (base+delta, base=blob.size/2)
    int vstream;             // varint streaming mode (INIT once, then payload-only frames)
    uint32_t streams;        // number of logical streams to interleave (vstream only)
} TxConfig;

static void* correction_listener_thread(void* arg){ (void)arg; // Placeholder for UDP NAK handling; real payload resend can be added
    // Intentionally minimal here to keep TX hot path uncontended.
    pause();
    return NULL;
}

int main(int argc, char** argv){
    signal(SIGINT,on_sigint);
TxConfig cfg={0}; cfg.ifname=NULL; cfg.queue=0; cfg.zerocopy=1; cfg.blob_size=2ULL<<30; cfg.huge_dir="/dev/hugepages"; cfg.blob_name="pfs_stream_blob"; cfg.seed=0x12345678ULL; cfg.desc_per_frame=64; cfg.total_bytes=1ULL<<30; cfg.duration_s=0.0; cfg.align=64; cfg.verbose=1; cfg.corr_listen=NULL; cfg.desc_file=NULL; cfg.mode_req=PFS_XDP_MODE_AUTO; cfg.arith=1; cfg.vstream=1; cfg.streams=4;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--ifname") && i+1<argc) cfg.ifname=argv[++i];
        else if(!strcmp(argv[i],"--queue") && i+1<argc) cfg.queue=(uint32_t)strtoul(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--no-zerocopy")) cfg.zerocopy=0;
        else if(!strcmp(argv[i],"--zerocopy") && i+1<argc) cfg.zerocopy=(int)strtoul(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--mode") && i+1<argc){ const char* m=argv[++i]; if(!strcmp(m,"drv")) cfg.mode_req=PFS_XDP_MODE_DRV; else if(!strcmp(m,"skb")) cfg.mode_req=PFS_XDP_MODE_SKB; else cfg.mode_req=PFS_XDP_MODE_AUTO; }
        else if(!strcmp(argv[i],"--arith") && i+1<argc) cfg.arith=(int)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--vstream") && i+1<argc) cfg.vstream=(int)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--streams") && i+1<argc) cfg.streams=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--blob-size") && i+1<argc) cfg.blob_size=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) cfg.huge_dir=argv[++i];
        else if(!strcmp(argv[i],"--blob-name") && i+1<argc) cfg.blob_name=argv[++i];
        else if(!strcmp(argv[i],"--seed") && i+1<argc) cfg.seed=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--desc-per-frame") && i+1<argc) cfg.desc_per_frame=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--total-bytes") && i+1<argc) cfg.total_bytes=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--duration") && i+1<argc) cfg.duration_s=strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"--align") && i+1<argc) cfg.align=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--quiet")) cfg.verbose=0;
        else if(!strcmp(argv[i],"--corr-listen") && i+1<argc) cfg.corr_listen=argv[++i];
        else if(!strcmp(argv[i],"--desc-file") && i+1<argc) cfg.desc_file=argv[++i];
        else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){
printf("Usage: %s --ifname IF --queue Q [--zerocopy 0|1] [--mode auto|drv|skb] [--arith 0|1] [--vstream 0|1] [--streams N] [--blob-size BYTES] [--huge-dir D] [--blob-name N]\n", argv[0]);
        printf("       [--seed S] [--desc-per-frame N] [--total-bytes B] [--duration S] [--align A] [--desc-file PATH] [--corr-listen HOST:PORT]\n");
            return 0;
        }
    }
    if(!cfg.ifname) die("--ifname required");
    if(cfg.duration_s>0) cfg.total_bytes=0; // time-bound

    if(cfg.verbose) fprintf(stderr,"[TX] if=%s q=%u zerocopy=%d blob=%zu dir=%s name=%s dpf=%u total=%llu dur=%.2f align=%u desc_file=%s\n",
        cfg.ifname,cfg.queue,cfg.zerocopy,(size_t)cfg.blob_size,cfg.huge_dir,cfg.blob_name,cfg.desc_per_frame,(unsigned long long)cfg.total_bytes,cfg.duration_s,cfg.align, cfg.desc_file?cfg.desc_file:"(none)");

    // Map or create persistent blob
    PfsHugeBlob blob; if(pfs_hugeblob_map(cfg.blob_size, cfg.huge_dir, cfg.blob_name, &blob)!=0) die("map blob: %s", strerror(errno)); pfs_hugeblob_set_keep(&blob,1);

    // Create UMEM/XSK for TX
PfsXdpUmem umem; if(pfs_xdp_umem_create(&umem, 0, 2048, 4096)!=0) die("umem create");
    PfsXdpSocket xsk; if(pfs_xdp_socket_create(&xsk, &umem, cfg.ifname, cfg.queue, 0, 1, cfg.zerocopy, cfg.mode_req)!=0) die("xsk create");
    if(cfg.verbose) fprintf(stderr, "[XDP] mode=%s zerocopy=%d if=%s q=%u\n", pfs_xdp_mode_str(xsk.mode), xsk.zerocopy_active, cfg.ifname, cfg.queue);

    // Optional correction listener thread (UDP NAKs)
    pthread_t corr_tid; if(cfg.corr_listen){ pthread_create(&corr_tid, NULL, correction_listener_thread, NULL); }

    // Optional descriptor list from file (CSV: offset,len per line)
    PfsGramDesc* desc_list = NULL; size_t desc_count = 0; size_t desc_idx = 0;
    if(cfg.desc_file){
        FILE* f = fopen(cfg.desc_file, "r"); if(!f) die("open desc-file: %s", strerror(errno));
        size_t cap = 1024; desc_list = (PfsGramDesc*)malloc(cap * sizeof(PfsGramDesc)); if(!desc_list) die("malloc desc_list");
        while(!feof(f)){
            unsigned long long off; unsigned long long len;
            int n = fscanf(f, "%llu,%llu", &off, &len);
            if(n == 2){
                if(off + len > blob.size){ // clamp within blob
                    if(len > blob.size) len = blob.size;
                    off = blob.size - len;
                    if(cfg.align) off &= ~((unsigned long long)cfg.align-1ULL);
                }
                if(desc_count == cap){ cap *= 2; PfsGramDesc* tmp = (PfsGramDesc*)realloc(desc_list, cap*sizeof(PfsGramDesc)); if(!tmp) die("realloc desc_list"); desc_list = tmp; }
                desc_list[desc_count].offset = (uint64_t)off; desc_list[desc_count].len = (uint32_t)len; desc_list[desc_count].flags = 0; desc_count++;
            } else {
                // skip line
                int c; while((c=fgetc(f))!='\n' && c!=EOF){}
            }
        }
        fclose(f);
        if(desc_count == 0) die("desc-file empty");
    }

    // Streaming loop: fill TX ring with frames containing descriptor-only schedules
    uint64_t seq=0, bytes_eff=0; uint64_t sent_frames=0; double t0=now_sec(), tlast=t0; uint64_t x=cfg.seed;
    const uint32_t dpf = cfg.desc_per_frame;
    const size_t hdrsz = sizeof(PfsXdpFrameHdr);
    const size_t descsz = sizeof(PfsGramDesc);
    const size_t framesz = hdrsz + dpf * descsz;
    if(framesz > umem.frame_size) die("desc-per-frame too large for frame_size=%u", umem.frame_size);

    int sent_init = 0; uint64_t desc_bytes_sum = 0;
    if(cfg.streams == 0 || cfg.streams > PFS_MAX_STREAMS) cfg.streams = 1;
    uint64_t prev_off_by_stream[PFS_MAX_STREAMS]; memset(prev_off_by_stream, 0, sizeof(prev_off_by_stream));
    uint64_t base = 0;
    while(!g_stop){
        if(cfg.total_bytes>0 && bytes_eff >= cfg.total_bytes) break;
        if(cfg.duration_s>0 && (now_sec()-t0) >= cfg.duration_s) break;
        uint32_t idx; int reserved = xsk_ring_prod__reserve(&xsk.tx, 1, &idx);
        if(reserved == 1){
            uint64_t addr = pfs_xdp_frame_addr(&umem, idx % umem.frame_count);
            void* p = pfs_xdp_frame_ptr(&umem, addr);
            if(cfg.vstream && !sent_init){
                // Send INIT header once to set session to varint streaming + arithmetic
                PfsXdpFrameHdr* h = (PfsXdpFrameHdr*)p; h->magic = 0x50565358u; h->version=2; h->flags=(uint16_t)((cfg.arith?1:0) | (1u<<2)); h->seq = seq++; h->desc_count=0; h->reserved=0;
                struct xdp_desc* txd0 = xsk_ring_prod__tx_desc(&xsk.tx, idx);
                txd0->addr = addr; txd0->len = (uint32_t)sizeof(PfsXdpFrameHdr);
                xsk_ring_prod__submit(&xsk.tx, 1); xsk.outstanding_tx++;
                sent_init = 1; continue;
            }
            if(cfg.vstream){
                // Write only varint payload + trailing hash with coalescing and aligned-length encoding
                uint8_t* out = (uint8_t*)p; size_t max = umem.frame_size; size_t pos = 0; base = blob.size/2; uint64_t eff_this=0;
                // Round-robin stream id
                static uint32_t rr = 0; uint32_t sid = rr++ % cfg.streams;
                // Encode stream_id as first varint
                uint64_t sidv = sid; while(sidv >= 0x80){ if(pos>=max) break; out[pos++] = (uint8_t)(sidv | 0x80); sidv >>= 7; } if(pos<max) out[pos++] = (uint8_t)sidv;
                // Coalesce pairs in a small buffer
                const uint32_t MAXP = 256; uint64_t off_buf[256]; uint32_t len_buf[256]; uint32_t pcnt=0;
                uint64_t prev_off = prev_off_by_stream[sid];
                // Determine align shift (power-of-two assumed for best results)
                uint32_t align = cfg.align ? cfg.align : 1; uint32_t shift=0; while(((1u<<shift) < align) && shift < 31) shift++;
                const uint32_t merge_gap = 64; // bytes
                for(uint32_t i=0;i<dpf && pcnt<MAXP;i++){
                    x = xorshift64(x);
                    uint32_t len = (uint32_t)((x % (align? (align*4):4096)) + align);
                    if(len > 262144u) len = 262144u;
                    // align len down to maintain unit encoding
                    if(align>1){ len &= ~(align-1u); if(len < align) len = align; }
                    uint64_t off = (x % (blob.size?blob.size:1));
                    if(align>1) off &= ~((uint64_t)align-1ULL);
                    if(off + len > blob.size){ if(len > blob.size) len = (uint32_t)blob.size; off = blob.size - len; if(align>1) off &= ~((uint64_t)align-1ULL); }
                    // Coalesce with previous buffered seg if close/adjacent
                    if(pcnt>0){ uint64_t last_off = off_buf[pcnt-1]; uint64_t last_len = len_buf[pcnt-1]; if(off <= last_off + last_len + merge_gap){ uint64_t new_end = off + len; uint64_t last_end = last_off + last_len; if(new_end > last_end){ len_buf[pcnt-1] = (uint32_t)(new_end - last_off); } continue; } }
                    off_buf[pcnt] = off; len_buf[pcnt] = len; pcnt++;
                }
                // Encode varints
                for(uint32_t i=0;i<pcnt;i++){
                    uint64_t off = off_buf[i]; uint32_t len = len_buf[i];
                    int64_t delta = (prev_off == 0 && i==0) ? (int64_t)(off - base) : (int64_t)(off - prev_off);
                    uint64_t zz = ((uint64_t)delta << 1) ^ (uint64_t)(delta >> 63);
                    while(zz >= 0x80){ if(pos>=max) break; out[pos++] = (uint8_t)(zz | 0x80); zz >>= 7; }
                    if(pos<max) out[pos++] = (uint8_t)zz; else break;
                    uint64_t Lq = (uint64_t)(len >> shift);
                    while(Lq >= 0x80){ if(pos>=max) break; out[pos++] = (uint8_t)(Lq | 0x80); Lq >>= 7; }
                    if(pos<max) out[pos++] = (uint8_t)Lq; else break;
                    prev_off = off; eff_this += len;
                    if(pos + 8 >= max) break;
                }
                // compute hash
                uint64_t h = 1469598103934665603ULL; size_t rpos = 0; uint64_t off_acc = prev_off_by_stream[sid] ? prev_off_by_stream[sid] : base; int first=1;
                while(rpos + 8 <= pos){
                    // decode delta
                    uint64_t u=0; int shift1=0; while(rpos < pos){ uint8_t b=((uint8_t*)p)[rpos++]; u |= ((uint64_t)(b & 0x7F)) << shift1; if(!(b & 0x80)) break; shift1 += 7; }
                    // decode len units
                    uint64_t Lu=0; shift1=0; while(rpos < pos){ uint8_t b=((uint8_t*)p)[rpos++]; Lu |= ((uint64_t)(b & 0x7F)) << shift1; if(!(b & 0x80)) break; shift1 += 7; }
                    uint64_t L = Lu << shift;
                    int64_t delta = (int64_t)((u >> 1) ^ (~(u & 1) + 1));
                    off_acc = first ? (base + delta) : (off_acc + delta); first=0;
                    if(off_acc + L <= blob.size){
                        const uint8_t* ptr = (const uint8_t*)blob.addr + off_acc; for(uint64_t k=0;k<L;k++){ h ^= ptr[k]; h *= 1099511628211ULL; }
                    }
                }
                if(pos + 8 <= max){ memcpy((uint8_t*)p + pos, &h, 8); pos += 8; }
                struct xdp_desc* txd = xsk_ring_prod__tx_desc(&xsk.tx, idx);
                txd->addr = addr; txd->len = (uint32_t)pos;
                xsk_ring_prod__submit(&xsk.tx, 1); xsk.outstanding_tx++;
                prev_off_by_stream[sid] = prev_off; // carry state per stream
                sent_frames++; bytes_eff += eff_this; desc_bytes_sum += pos;
                continue;
            }
            // Legacy header + fixed descriptors
            PfsXdpFrameHdr* h = (PfsXdpFrameHdr*)p; h->magic = 0x50565358u; h->version=1; h->flags=(uint16_t)(cfg.arith?1:0); h->seq = seq++; h->desc_count=(uint16_t)dpf; h->reserved=0;
            PfsGramDesc* d = (PfsGramDesc*)((uint8_t*)p + hdrsz);
            uint64_t eff_this=0; uint64_t prev_off=0; uint64_t base=blob.size/2;
            for(uint32_t i=0;i<dpf;i++){
if(desc_list){
                    // wrap around for duration-bound runs
                    if(desc_idx >= desc_count) desc_idx = 0;
                    PfsGramDesc src = desc_list[desc_idx++];
                    uint64_t off = src.offset; uint32_t len = src.len;
                    if(cfg.arith){ d[i].offset = (i==0) ? (off - base) : (off - prev_off); prev_off = off; d[i].len = len; d[i].flags = 0; }
                    else { d[i] = src; }
                    eff_this += len;
                } else {
                    x = xorshift64(x);
                    uint32_t len = (uint32_t)((x % (cfg.align? (cfg.align*4):4096)) + cfg.align); // small segments
                    if(len > 262144u) len = 262144u; // cap
                    uint64_t off = (x % (blob.size?blob.size:1));
                    if(cfg.align) off &= ~((uint64_t)cfg.align-1ULL);
                    if(off + len > blob.size){ if(len > blob.size) len = (uint32_t)blob.size; off = blob.size - len; if(cfg.align) off &= ~((uint64_t)cfg.align-1ULL); }
                    if(cfg.arith){ d[i].offset = (i==0) ? (off - base) : (off - prev_off); prev_off = off; d[i].len = len; d[i].flags = 0; }
                    else { d[i].offset = off; d[i].len = len; d[i].flags = 0; }
                    eff_this += len;
                }
            }
            // Populate TX descriptor
            struct xdp_desc* txd = xsk_ring_prod__tx_desc(&xsk.tx, idx);
            txd->addr = addr; txd->len = (uint32_t)framesz;
            xsk_ring_prod__submit(&xsk.tx, 1); xsk.outstanding_tx++;
            sent_frames++; bytes_eff += eff_this;
        } else {
            // Reap completions
            uint32_t idx_cq; unsigned int r = xsk_ring_cons__peek(&umem.cq, 64, &idx_cq);
            if(r){ xsk_ring_cons__release(&umem.cq, r); if(xsk.outstanding_tx >= r) xsk.outstanding_tx -= r; }
            // Nudge kernel
            sendto(xsk_socket__fd(xsk.xsk), NULL, 0, MSG_DONTWAIT, NULL, 0);
        }
        double tn=now_sec(); if(cfg.verbose && (tn - tlast) >= 0.5){ double mb = bytes_eff/1e6; double mbps = mb/(tn - t0); fprintf(stderr,"[TX] eff=%.1f MB avg=%.1f MB/s frames=%llu\n", mb, mbps, (unsigned long long)sent_frames); tlast=tn; }
    }
    // Final flush
    while(xsk.outstanding_tx){ uint32_t idx_cq; unsigned int r = xsk_ring_cons__peek(&umem.cq, 64, &idx_cq); if(r){ xsk_ring_cons__release(&umem.cq, r); if(xsk.outstanding_tx>=r) xsk.outstanding_tx -= r; } else break; }

double t1=now_sec(); double mb = bytes_eff/1e6; double mbps = mb/(t1 - t0 + 1e-9);
    if(cfg.vstream){ double db = desc_bytes_sum/1e6; double ratio = desc_bytes_sum? ( (double)desc_bytes_sum / (double)bytes_eff ) : 0.0; fprintf(stderr,"[TX DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames=%llu desc_bytes=%llu (%.3f MB) desc_ratio=%.6f\n", (unsigned long long)bytes_eff, mb, (t1-t0), mbps, (unsigned long long)sent_frames, (unsigned long long)desc_bytes_sum, db, ratio); }
    else { fprintf(stderr,"[TX DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames=%llu\n", (unsigned long long)bytes_eff, mb, (t1-t0), mbps, (unsigned long long)sent_frames); }

    if(cfg.corr_listen){ pthread_kill(corr_tid, SIGINT); pthread_join(corr_tid,NULL); }
    if(desc_list) free(desc_list);
    pfs_xdp_socket_destroy(&xsk); pfs_xdp_umem_destroy(&umem); pfs_hugeblob_unmap(&blob); return 0;
}

