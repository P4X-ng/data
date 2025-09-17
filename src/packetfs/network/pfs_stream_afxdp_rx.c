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
#include <bpf/libbpf.h>
#include <bpf/bpf.h>
#include <linux/if_link.h>

// pCPU apply
#include "../pcpu/pfs_pcpu.h"

// Varint helpers (mirror SHM bench for varint streaming mode)
static inline uint64_t zz_enc64(int64_t v){ return ((uint64_t)v << 1) ^ (uint64_t)(v >> 63); }
static inline int64_t zz_dec64(uint64_t u){ return (int64_t)((u >> 1) ^ (~(u & 1) + 1)); }
static inline size_t uvarint_dec_rx(const uint8_t* in, size_t max, uint64_t* out){ uint64_t v=0; int shift=0; size_t i=0; while(i<max){ uint8_t b=in[i++]; v |= ((uint64_t)(b & 0x7F)) << shift; if(!(b & 0x80)){ *out=v; return i; } shift += 7; if(shift>63) break; } return 0; }

#include "pfs_stream_afxdp.h"
#include "../memory/pfs_hugeblob.h"
#include "../gram/pfs_gram.h"

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

// Frame header (must match TX)
typedef struct {
    uint32_t magic;     // 'PFSX'
    uint16_t version;
    uint16_t flags;     // bit0: arithmetic mode (base+delta)
    uint64_t seq;
    uint16_t desc_count;
    uint16_t reserved;
} __attribute__((packed)) PfsXdpFrameHdr;

static void die(const char* fmt, ...){ va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);} 

// Simple rolling integrity checksum (FNV-1a 64)
static inline uint64_t fnv1a64_init(void){ return 1469598103934665603ULL; }
static inline uint64_t fnv1a64_update(uint64_t h, const void* data, size_t n){ const uint8_t* p=(const uint8_t*)data; for(size_t i=0;i<n;i++){ h ^= p[i]; h *= 1099511628211ULL; } return h; }


typedef struct {
    const char* ifname;
    uint32_t queue;
    int zerocopy;
    size_t blob_size;
    const char* huge_dir;
    const char* blob_name;
    int verbose;
    const char* corr_target; // host:port for NAKs (optional)
    const char* bpf_obj; // path to compiled XDP object
    PfsXdpMode mode_req;     // requested XDP mode
    // pCPU execution controls
    int pcpu_enable;         // 1 to apply pCPU op on decoded spans
    pfs_pcpu_op_t pcpu_op;   // operation
    uint8_t pcpu_imm;        // immediate (for xor/add)
} RxConfig;

static void* checksum_thread(void* arg){
    // This thread could periodically scan selected offsets to verify residency/integrity (optional).
    // Placeholder: sleep until stop; real implementations can add sampling.
    while(!g_stop){ struct timespec ts={0,200*1000*1000}; nanosleep(&ts,NULL);} return NULL;
}

int main(int argc, char** argv){
    signal(SIGINT,on_sigint);
RxConfig cfg={0}; cfg.ifname=NULL; cfg.queue=0; cfg.zerocopy=1; cfg.blob_size=2ULL<<30; cfg.huge_dir="/dev/hugepages"; cfg.blob_name="pfs_stream_blob"; cfg.verbose=1; cfg.corr_target=NULL; cfg.bpf_obj="dev/wip/native/pfs_xdp_redirect_kern.o"; cfg.mode_req=PFS_XDP_MODE_AUTO;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--ifname") && i+1<argc) cfg.ifname=argv[++i];
        else if(!strcmp(argv[i],"--queue") && i+1<argc) cfg.queue=(uint32_t)strtoul(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--no-zerocopy")) cfg.zerocopy=0;
        else if(!strcmp(argv[i],"--zerocopy") && i+1<argc) cfg.zerocopy=(int)strtoul(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--mode") && i+1<argc){ const char* m=argv[++i]; if(!strcmp(m,"drv")) cfg.mode_req=PFS_XDP_MODE_DRV; else if(!strcmp(m,"skb")) cfg.mode_req=PFS_XDP_MODE_SKB; else cfg.mode_req=PFS_XDP_MODE_AUTO; }
        else if(!strcmp(argv[i],"--pcpu") && i+1<argc) cfg.pcpu_enable=(int)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pcpu-op") && i+1<argc){ const char* o=argv[++i]; if(!strcmp(o,"fnv")||!strcmp(o,"fnv64")) cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_FNV64; else if(!strcmp(o,"xor")) cfg.pcpu_op=PFS_PCPU_OP_XOR_IMM8; else if(!strcmp(o,"add")) cfg.pcpu_op=PFS_PCPU_OP_ADD_IMM8; else if(!strcmp(o,"crc32c")) cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_CRC32C; else if(!strcmp(o,"counteq")) cfg.pcpu_op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
        else if(!strcmp(argv[i],"--imm") && i+1<argc) cfg.pcpu_imm=(uint8_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--blob-size") && i+1<argc) cfg.blob_size=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) cfg.huge_dir=argv[++i];
        else if(!strcmp(argv[i],"--blob-name") && i+1<argc) cfg.blob_name=argv[++i];
        else if(!strcmp(argv[i],"--quiet")) cfg.verbose=0;
        else if(!strcmp(argv[i],"--corr-target") && i+1<argc) cfg.corr_target=argv[++i];
        else if(!strcmp(argv[i],"--bpf-obj") && i+1<argc) cfg.bpf_obj=argv[++i];
        else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){
printf("Usage: %s --ifname IF --queue Q [--zerocopy 0|1] [--mode auto|drv|skb] [--blob-size BYTES] [--huge-dir D] [--blob-name N] [--corr-target HOST:PORT]\n", argv[0]);
            return 0;
        }
    }
    if(!cfg.ifname) die("--ifname required");
    if(cfg.verbose) fprintf(stderr,"[RX] if=%s q=%u zerocopy=%d blob=%zu dir=%s name=%s bpf=%s pcpu=%d op=%d imm=%u\n", cfg.ifname,cfg.queue,cfg.zerocopy,(size_t)cfg.blob_size,cfg.huge_dir,cfg.blob_name,cfg.bpf_obj,cfg.pcpu_enable,(int)cfg.pcpu_op,(unsigned)cfg.pcpu_imm);

    // Map/create persistent blob
    PfsHugeBlob blob; if(pfs_hugeblob_map(cfg.blob_size, cfg.huge_dir, cfg.blob_name, &blob)!=0) die("map blob: %s", strerror(errno)); pfs_hugeblob_set_keep(&blob,1);

    // Create UMEM/XSK for RX
PfsXdpUmem umem; if(pfs_xdp_umem_create(&umem, 0, 2048, 8192)!=0) die("umem create");
    PfsXdpSocket xsk; if(pfs_xdp_socket_create(&xsk, &umem, cfg.ifname, cfg.queue, 1, 0, cfg.zerocopy, cfg.mode_req)!=0) die("xsk create");
    if(cfg.verbose) fprintf(stderr, "[XDP] mode=%s zerocopy=%d if=%s q=%u\n", pfs_xdp_mode_str(xsk.mode), xsk.zerocopy_active, cfg.ifname, cfg.queue);

    // Load and attach XDP program (force SKB/generic mode on veth);
    // update xsks_map with xsk fd before attaching.
    struct bpf_object* obj = bpf_object__open_file(cfg.bpf_obj, NULL);
    if(!obj) die("bpf_object__open_file %s", cfg.bpf_obj);
    if(bpf_object__load(obj) != 0) die("bpf_object__load: %s", strerror(errno));

    struct bpf_map* map = bpf_object__find_map_by_name(obj, "xsks_map");
    if(!map) die("xsks_map not found");
    int map_fd = bpf_map__fd(map);
    int xsk_fd = xsk_socket__fd(xsk.xsk);
    __u32 key = cfg.queue;
    if(bpf_map_update_elem(map_fd, &key, &xsk_fd, 0) != 0)
        die("bpf_map_update_elem xsks_map: %s", strerror(errno));

    struct bpf_program* prog = bpf_object__find_program_by_name(obj, "xdp_redirect");
    if(!prog) die("xdp_redirect not found");

    int ifindex = if_nametoindex(cfg.ifname);
    if(ifindex==0) die("if_nametoindex %s", cfg.ifname);

    // Prefer generic (skb) mode for maximum compatibility on veth
    int prog_fd = bpf_program__fd(prog);
    int ret;
    // Try to attach in driver (native) mode first; if fails, try generic (skb)
    ret = bpf_xdp_attach(ifindex, prog_fd, XDP_FLAGS_DRV_MODE | XDP_FLAGS_UPDATE_IF_NOEXIST, NULL);
    if(ret < 0){
        (void)bpf_xdp_detach(ifindex, XDP_FLAGS_DRV_MODE, NULL);
        ret = bpf_xdp_attach(ifindex, prog_fd, XDP_FLAGS_DRV_MODE, NULL);
    }
    if(ret < 0){
        // Fallback to SKB mode
        (void)bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
        ret = bpf_xdp_attach(ifindex, prog_fd, XDP_FLAGS_SKB_MODE | XDP_FLAGS_UPDATE_IF_NOEXIST, NULL);
        if(ret < 0){
            (void)bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
            ret = bpf_xdp_attach(ifindex, prog_fd, XDP_FLAGS_SKB_MODE, NULL);
        }
    }
    if(ret < 0){
        int err = -ret;
        die("attach xdp failed: %s", strerror(err>0?err:errno));
    }

    // Prefill RX FILL ring with all frames
    uint32_t idx; unsigned int n = xsk_ring_prod__reserve(&umem.fq, umem.frame_count, &idx);
    for(unsigned int i=0;i<n;i++){ *xsk_ring_prod__fill_addr(&umem.fq, idx+i) = pfs_xdp_frame_addr(&umem, i); }
    xsk_ring_prod__submit(&umem.fq, n);

    pthread_t cs_tid; pthread_create(&cs_tid,NULL,checksum_thread,NULL);

    // Streaming receive loop
    uint64_t bytes_eff=0, frames=0; double t0=now_sec(), tlast=t0; uint64_t csum = fnv1a64_init();
    int session_vstream = 0; int session_arith = 0; uint64_t desc_bytes_sum = 0;
    // pCPU metrics aggregate
    pfs_pcpu_metrics_t pcpu_m = {0};
    int l2_skip = 0; // optional future flag to align AF_XDP with DPDK when L2 present
    uint64_t per_stream_bytes[256]; memset(per_stream_bytes, 0, sizeof(per_stream_bytes));
    uint64_t per_stream_desc_bytes[256]; memset(per_stream_desc_bytes, 0, sizeof(per_stream_desc_bytes));
    uint64_t per_stream_frames[256]; memset(per_stream_frames, 0, sizeof(per_stream_frames));
    while(!g_stop){
        uint32_t idx_rx; unsigned int r = xsk_ring_cons__peek(&xsk.rx, 64, &idx_rx);
        if(!r){ // kick kernel and wait a bit
            recvfrom(xsk_socket__fd(xsk.xsk), NULL, 0, MSG_DONTWAIT, NULL, NULL);
            struct pollfd pfd={ .fd=xsk_socket__fd(xsk.xsk), .events=POLLIN };
            poll(&pfd, 1, 10);
            continue;
        }
        for(unsigned int i=0;i<r;i++){
            const struct xdp_desc* rx = xsk_ring_cons__rx_desc(&xsk.rx, idx_rx + i);
            void* p = pfs_xdp_frame_ptr(&umem, rx->addr);
            if(!session_vstream){
                if(rx->len >= sizeof(PfsXdpFrameHdr)){
                    PfsXdpFrameHdr* h = (PfsXdpFrameHdr*)p; if(h->magic == 0x50565358u){
                        if(h->desc_count == 0 && (h->version >= 2) && (h->flags & (1u<<2))){ session_vstream = 1; session_arith = (h->flags & 1u) ? 1 : 0; continue; }
                        if(h->version == 1){
                            size_t ndesc = h->desc_count; size_t need = sizeof(PfsXdpFrameHdr) + ndesc * sizeof(PfsGramDesc);
                            if(rx->len < need) continue;
                            PfsGramDesc* d = (PfsGramDesc*)((uint8_t*)p + sizeof(PfsXdpFrameHdr));
                            uint64_t base = blob.size/2; uint64_t off_acc=base;
                            for(size_t k=0;k<ndesc;k++){
                                uint64_t off = d[k].offset; uint32_t len = d[k].len;
                                if(h->flags & 1u){ if(k==0){ off = base + off; off_acc = off; } else { off_acc += off; off = off_acc; } }
                                if(off+len <= blob.size){ csum = fnv1a64_update(csum, (uint8_t*)blob.addr + off, len); bytes_eff += len; }
                            }
                            frames++;
                            continue;
                        }
                    }
                }
            }
            // Varint streaming payload (no header), trailing 8-byte hash
            if(session_vstream){
                if(rx->len < 8) continue;
                const uint8_t* buf = (const uint8_t*)p; size_t plen = rx->len; size_t pos = (l2_skip>0 && (size_t)l2_skip<plen)? (size_t)l2_skip : 0; uint64_t base = blob.size/2; uint64_t eff=0;
                // First varint: stream_id
                uint64_t sid=0; size_t m0 = uvarint_dec_rx(buf+pos, plen - 8 - pos, &sid); if(!m0){ continue; } pos += m0; sid &= 0xFF;
                static uint64_t last_off_by_stream[256]; uint64_t off_acc = last_off_by_stream[sid] ? last_off_by_stream[sid] : base; int first= last_off_by_stream[sid] ? 0 : 1;
                // Collect descs for pCPU apply if enabled
                PfsGramDesc descs[1024]; size_t dcnt=0;
                // Parse until trailing hash
                while(pos + 8 <= plen){
                    uint64_t u; size_t m = uvarint_dec_rx(buf+pos, plen - 8 - pos, &u); if(!m) break; pos += m;
                    uint64_t Lu; size_t m2 = uvarint_dec_rx(buf+pos, plen - 8 - pos, &Lu); if(!m2) break; pos += m2;
                    int64_t delta = zz_dec64(u);
                    uint64_t L = Lu; // units already reflect alignment
                    off_acc = first ? (base + delta) : (off_acc + delta); first=0;
                    if(off_acc + L <= blob.size){
                        csum = fnv1a64_update(csum, (uint8_t*)blob.addr + off_acc, (size_t)L);
                        bytes_eff += L; eff += L;
                        if(cfg.pcpu_enable && dcnt < 1024){ descs[dcnt].offset = off_acc; descs[dcnt].len = (uint32_t)L; descs[dcnt].flags = 0; dcnt++; }
                    }
                }
                if(cfg.pcpu_enable && dcnt){ pfs_pcpu_metrics_t m; memset(&m,0,sizeof(m)); (void)pfs_pcpu_apply(blob.addr, blob.size, descs, dcnt, cfg.pcpu_op, cfg.pcpu_imm, 1469598103934665603ULL, &m); pcpu_m.bytes_total += m.bytes_total; pcpu_m.bytes_touched += m.bytes_touched; pcpu_m.desc_count += m.desc_count; pcpu_m.ns += m.ns; pcpu_m.checksum_out ^= m.checksum_out; }
                last_off_by_stream[sid] = off_acc;
                desc_bytes_sum += rx->len;
                per_stream_bytes[sid] += eff; per_stream_desc_bytes[sid] += rx->len; per_stream_frames[sid]++;
                frames++;
                continue;
            }
        }
        xsk_ring_cons__release(&xsk.rx, r);
        // Recycle frames back to FILL
        unsigned int pushed=0; while(pushed<r){ uint32_t idx_fq; unsigned int m = xsk_ring_prod__reserve(&umem.fq, r-pushed, &idx_fq); if(!m) break; for(unsigned int j=0;j<m;j++){ *xsk_ring_prod__fill_addr(&umem.fq, idx_fq+j) = pfs_xdp_frame_addr(&umem, (idx_rx + pushed + j) % umem.frame_count); } xsk_ring_prod__submit(&umem.fq, m); pushed += m; }

        double tn=now_sec(); if(cfg.verbose && (tn - tlast) >= 0.5){ double mb = bytes_eff/1e6; double mbps = mb/(tn - t0); fprintf(stderr,"[RX] eff=%.1f MB avg=%.1f MB/s frames=%llu\n", mb, mbps, (unsigned long long)frames); tlast=tn; }
    }

double t1=now_sec(); double mb = bytes_eff/1e6; double mbps = mb/(t1 - t0 + 1e-9);
    if(session_vstream){ double db = desc_bytes_sum/1e6; double ratio = desc_bytes_sum? ( (double)desc_bytes_sum / (double)bytes_eff ) : 0.0; fprintf(stderr,"[RX DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s checksum=0x%016llx frames=%llu desc_bytes=%llu (%.3f MB) desc_ratio=%.6f\n", (unsigned long long)bytes_eff, mb, (t1-t0), mbps, (unsigned long long)csum, (unsigned long long)frames, (unsigned long long)desc_bytes_sum, db, ratio);
        if(cfg.pcpu_enable){ double pc_mb = pcpu_m.bytes_touched/1e6; double pc_mbps = (t1>t0)? (pc_mb/((t1-t0))) : 0.0; fprintf(stderr,"[RX PCPU] touched=%.3f MB desc=%llu time=%.3f s pcpu_MBps=%.1f op=%d imm=%u\n", pc_mb, (unsigned long long)pcpu_m.desc_count, (double)pcpu_m.ns/1e9, pc_mbps, (int)cfg.pcpu_op, (unsigned)cfg.pcpu_imm); }
        // Per-stream summary (top few)
        for(int s=0;s<256;s++){ if(per_stream_frames[s]){ double smb = per_stream_bytes[s]/1e6; double sratio = per_stream_desc_bytes[s]? ((double)per_stream_desc_bytes[s]/(double)per_stream_bytes[s]) : 0.0; fprintf(stderr,"  [stream %d] eff=%.1f MB frames=%llu desc_ratio=%.6f\n", s, smb, (unsigned long long)per_stream_frames[s], sratio); } }
    }
    else { fprintf(stderr,"[RX DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s checksum=0x%016llx frames=%llu\n", (unsigned long long)bytes_eff, mb, (t1-t0), mbps, (unsigned long long)csum, (unsigned long long)frames); }

    pthread_kill(cs_tid, SIGINT); pthread_join(cs_tid,NULL);
    // Detach XDP program and cleanup
    (void)bpf_xdp_detach(ifindex, XDP_FLAGS_SKB_MODE, NULL);
    if(obj) bpf_object__close(obj);
    pfs_xdp_socket_destroy(&xsk); pfs_xdp_umem_destroy(&umem); pfs_hugeblob_unmap(&blob); return 0;
}

