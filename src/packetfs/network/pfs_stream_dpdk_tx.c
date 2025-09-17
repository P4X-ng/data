#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

// DPDK
#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_ether.h>
#include <rte_mbuf.h>
#include <rte_mempool.h>
#include <rte_lcore.h>
#include <rte_cycles.h>

// PacketFS
#include "../memory/pfs_hugeblob.h"
#include "../gram/pfs_gram.h"

#define PFS_MAX_STREAMS 256
#define PFS_MBUF_POOL_NAME "pfs_dpdk_pool"
#define PFS_CACHE_SIZE 512
#define PFS_NB_MBUFS (8192*4)
#define PFS_BURST 32

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void die(const char* fmt, ...){ va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);} 

static inline uint64_t xorshift64(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }

// zigzag encode
static inline uint64_t zz_enc64(int64_t v){ return ((uint64_t)v << 1) ^ (uint64_t)(v >> 63); }

// uvarint encoder, returns bytes written
static inline size_t uvarint_enc(uint8_t* out, size_t max, uint64_t v){ size_t i=0; while(v >= 0x80){ if(i>=max) return 0; out[i++] = (uint8_t)(v | 0x80); v >>= 7; } if(i>=max) return 0; out[i++] = (uint8_t)v; return i; }

// Simple header to signal varint streaming (compatible with AF_XDP header)
typedef struct __attribute__((packed)) {
    uint32_t magic;   // 'PFSX' 0x50565358
    uint16_t version; // 2 for varint streaming
    uint16_t flags;   // bit0: arith, bit2: vstream
    uint64_t seq;
    uint16_t desc_count; // 0 for INIT
    uint16_t reserved;
} PfsXdpFrameHdr;

// Minimal protocol header to precede varint payload (for vdev/AF_PACKET friendliness)
// Magic 'PVRT' (0x50565254), version=1, align_shift conveys TX alignment units
// payload_len bounds the varint region (excludes trailing 8-byte hash). Layout matches RX.
typedef struct __attribute__((packed)) {
    uint32_t magic;       // 'PVRT'
    uint8_t  version;     // 1
    uint8_t  align_shift; // shift applied to length units
    uint16_t payload_len; // bytes of varint payload following this header
    uint8_t  flags;       // reserved (future)
    uint8_t  rsvd;        // pad
} PfsVarintHdr;

typedef struct {
    // Single-core, multi-port, multi-queue configuration
    int ports[32];          // list of port ids
    int n_ports;            // number of active ports
    const char* ports_csv;  // optional CSV for --ports (e.g., "0,1")
    const char* pcis_csv;   // optional CSV for --pcis (e.g., "0000:65:00.0,0000:66:00.0")
    int tx_queues;          // queues per port (round-robin on single core)

    const char* eal;        // optional EAL args string (e.g., "-l 0 -n 4")
    size_t blob_size;       // blob backing store
    const char* huge_dir;   // where to map blob if hugetlbfs
    const char* blob_name;  // blob filename
    uint64_t seed;
    uint32_t desc_per_frame; // generator guidance only
    uint64_t total_bytes;    // 0 -> time-bound
    double duration_s;       // 0 -> byte-bound
    uint32_t align;          // power-of-two alignment for offsets/len units
    int verbose;
    int arith;               // base+delta encoding wrt base or last off per stream
    int vstream;             // true: varint mode
    uint32_t streams;        // number of logical streams
    int eth_hdr;             // prepend Ethernet header (dst broadcast) when set
    int proto_hdr;           // prepend PfsVarintHdr before varints
    int secondary;           // run as EAL secondary: do not (re)configure/start the port
} TxConfig;

static int parse_kv(int argc, char** argv, const char* key, const char** out){
    for(int i=1;i<argc-1;i++){ if(strcmp(argv[i], key)==0){ *out = argv[i+1]; return 1; } }
    return 0;
}

static void build_eal_argv(const char* eal_str, int* out_argc, char*** out_argv){
    // Default minimal EAL: "-l 0 -n 4"
    const char* def = "-l 0 -n 4";
    const char* s = (eal_str && *eal_str) ? eal_str : def;
    // Count tokens
    int count = 1; // program name
    for(const char* p=s; *p; p++){ if(*p==' ') count++; }
    // Allocate
    char** av = (char**)calloc((size_t)count+2, sizeof(char*));
    int ac = 0;
    av[ac++] = strdup("pfs_dpdk");
    // Tokenize (simple whitespace split)
    char* tmp = strdup(s);
    char* save=NULL; char* tok = strtok_r(tmp, " ", &save);
    while(tok){ av[ac++] = strdup(tok); tok = strtok_r(NULL, " ", &save);} 
    av[ac] = NULL;
    *out_argc = ac; *out_argv = av; free(tmp);
}

int main(int argc, char** argv){
    signal(SIGINT, on_sigint);
    TxConfig cfg; memset(&cfg, 0, sizeof(cfg));
    cfg.n_ports=0; cfg.ports_csv=NULL; cfg.pcis_csv=NULL; cfg.tx_queues=1; cfg.eal=NULL; cfg.blob_size=2ULL<<30; cfg.huge_dir="/dev/hugepages"; cfg.blob_name="pfs_stream_blob";
    cfg.seed=0x12345678ULL; cfg.desc_per_frame=64; cfg.total_bytes=0; cfg.duration_s=10.0; cfg.align=64; cfg.verbose=1; cfg.arith=1; cfg.vstream=1; cfg.streams=4;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--port") && i+1<argc){ // backward-compat single port
            cfg.ports[0] = (int)strtol(argv[++i],NULL,10); cfg.n_ports=1;
        }
        else if(!strcmp(argv[i],"--ports") && i+1<argc) cfg.ports_csv = argv[++i];
        else if(!strcmp(argv[i],"--pcis") && i+1<argc) cfg.pcis_csv = argv[++i];
        else if(!strcmp(argv[i],"--tx-queues") && i+1<argc) cfg.tx_queues = (int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--eal") && i+1<argc) cfg.eal = argv[++i];
        else if(!strcmp(argv[i],"--blob-size") && i+1<argc) cfg.blob_size = strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) cfg.huge_dir = argv[++i];
        else if(!strcmp(argv[i],"--blob-name") && i+1<argc) cfg.blob_name = argv[++i];
        else if(!strcmp(argv[i],"--seed") && i+1<argc) cfg.seed = strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--desc-per-frame") && i+1<argc) cfg.desc_per_frame=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--total-bytes") && i+1<argc) cfg.total_bytes = strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--duration") && i+1<argc) cfg.duration_s = strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"--align") && i+1<argc) cfg.align=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--eth") && i+1<argc) cfg.eth_hdr = (int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--proto-hdr") && i+1<argc) cfg.proto_hdr = (int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--quiet")) cfg.verbose=0;
        else if(!strcmp(argv[i],"--arith") && i+1<argc) cfg.arith=(int)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--vstream") && i+1<argc) cfg.vstream=(int)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--streams") && i+1<argc) cfg.streams=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--secondary") && i+1<argc) cfg.secondary=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")){
            printf("Usage: %s [--ports CSV | --pcis CSV | --port N] [--tx-queues N] [--eal \"-l 0 -n 4\"]\n", argv[0]);
            printf("           [--blob-size B] [--seed S] [--desc-per-frame N] [--total-bytes B | --duration S]\n");
            printf("           [--align A] [--arith 0|1] [--vstream 0|1] [--streams N] [--secondary 0|1]\n");
            return 0;
        }
    }
    if(cfg.duration_s>0) cfg.total_bytes=0;
    if(cfg.streams==0 || cfg.streams>PFS_MAX_STREAMS) cfg.streams=1;
    if(cfg.tx_queues <= 0) cfg.tx_queues = 1;

    // Map blob; exclude setup from timing
    PfsHugeBlob blob; if(pfs_hugeblob_map(cfg.blob_size, cfg.huge_dir, cfg.blob_name, &blob)!=0) die("map blob: %s", strerror(errno)); pfs_hugeblob_set_keep(&blob,1);

    // EAL init
    int eal_argc=0; char** eal_argv=NULL; build_eal_argv(cfg.eal, &eal_argc, &eal_argv);
    int ret = rte_eal_init(eal_argc, eal_argv);
    if(ret < 0){ die("rte_eal_init failed; ensure hugepages configured (try: just hugepages-status)"); }

    // Resolve ports from CSVs if provided
        if(cfg.pcis_csv && *cfg.pcis_csv){
            // Parse comma-separated PCI names
            char* tmp = strdup(cfg.pcis_csv); char* save=NULL; char* tok = strtok_r(tmp, ",", &save);
            while(tok && cfg.n_ports < (int)(sizeof(cfg.ports)/sizeof(cfg.ports[0]))){
                uint16_t pid16=0; if(rte_eth_dev_get_port_by_name(tok, &pid16)==0 && rte_eth_dev_is_valid_port(pid16)) cfg.ports[cfg.n_ports++] = (int)pid16; tok = strtok_r(NULL, ",", &save);
            }
            free(tmp);
        }
    if(cfg.ports_csv && *cfg.ports_csv){
        char* tmp = strdup(cfg.ports_csv); char* save=NULL; char* tok = strtok_r(tmp, ",", &save);
        while(tok && cfg.n_ports < (int)(sizeof(cfg.ports)/sizeof(cfg.ports[0]))){
            int pid = (int)strtol(tok,NULL,10); if(rte_eth_dev_is_valid_port(pid)) cfg.ports[cfg.n_ports++] = pid; tok = strtok_r(NULL, ",", &save);
        }
        free(tmp);
    }
    if(cfg.n_ports == 0){ // default to port 0 if available
        if(rte_eth_dev_is_valid_port(0)) { cfg.ports[0]=0; cfg.n_ports=1; }
        else die("no valid DPDK ports available");
    }

    if(cfg.verbose){
        fprintf(stderr, "[TX-DPDK] ports="); for(int i=0;i<cfg.n_ports;i++){ fprintf(stderr, "%s%d", (i?",":""), cfg.ports[i]); } fprintf(stderr, " txq=%d eal=\"%s\" blob=%zu dir=%s name=%s dpf=%u dur=%.2f align=%u arith=%d vstream=%d streams=%u\n",
            cfg.tx_queues, cfg.eal?cfg.eal:"-l 0 -n 4", (size_t)cfg.blob_size, cfg.huge_dir, cfg.blob_name, cfg.desc_per_frame, cfg.duration_s, cfg.align, cfg.arith, cfg.vstream, cfg.streams);
    }

    // Create mempool (shared within this process only)
    unsigned int nb_mbufs = PFS_NB_MBUFS * (unsigned int)cfg.n_ports;
    struct rte_mempool* mp = rte_pktmbuf_pool_create(PFS_MBUF_POOL_NAME, nb_mbufs, PFS_CACHE_SIZE, 0, RTE_MBUF_DEFAULT_BUF_SIZE, rte_socket_id());
    if(!mp) die("mbuf pool create failed: %s", rte_strerror(rte_errno));

    int is_secondary = (cfg.secondary != 0) || (rte_eal_process_type() == RTE_PROC_SECONDARY);

    if(!is_secondary){
        // Configure all ports with tx_queues queues
        struct rte_eth_conf port_conf; memset(&port_conf, 0, sizeof(port_conf));
        port_conf.rxmode.mq_mode = RTE_ETH_MQ_RX_NONE;
        port_conf.txmode.mq_mode = RTE_ETH_MQ_TX_NONE;
        for(int i=0;i<cfg.n_ports;i++){
            int pid = cfg.ports[i];
            // Some PMDs (e.g., r8169) require at least one RX queue even in TX-only to avoid crashes in dev_start.
            int rxq_min = 1;
            if(rte_eth_dev_configure(pid, rxq_min, cfg.tx_queues, &port_conf) < 0) die("rte_eth_dev_configure port %d", pid);
            // Minimal RX queue to satisfy PMD requirements; we will not receive in TX tool.
            if(rte_eth_rx_queue_setup(pid, 0, 1024, rte_eth_dev_socket_id(pid), NULL, mp) < 0) die("rx_queue_setup port %d q0", pid);
            for(int q=0;q<cfg.tx_queues;q++){
                if(rte_eth_tx_queue_setup(pid, q, 1024, rte_eth_dev_socket_id(pid), NULL) < 0) die("tx_queue_setup port %d q%d", pid, q);
            }
            if(rte_eth_dev_start(pid) < 0) die("rte_eth_dev_start port %d", pid);
        }
    } else {
        if(cfg.verbose){ fprintf(stderr, "[TX-DPDK] secondary process: skipping ethdev configure/start; using existing queues\n"); }
    }

    // Streaming loop
    uint64_t bytes_eff=0, sent_frames=0, desc_bytes_sum=0; double t0=now_sec(), tlast=t0; uint64_t x=cfg.seed; uint64_t seq=0;
    // Counters
    uint64_t c_alloc_fail=0, c_append_fail=0, c_tx_zero=0, c_encode_fail=0, c_tailroom_skip=0;
    int sent_init = 0;
    uint64_t prev_off_by_stream[PFS_MAX_STREAMS]; memset(prev_off_by_stream, 0, sizeof(prev_off_by_stream));

    // Round-robin indices
    int rr_port = 0; int rr_q = 0;

    while(!g_stop){
        if(cfg.total_bytes>0 && bytes_eff >= cfg.total_bytes) break;
        if(cfg.duration_s>0 && (now_sec()-t0) >= cfg.duration_s) break;

        struct rte_mbuf* m = rte_pktmbuf_alloc(mp);
        if(!m){ c_alloc_fail++; rte_delay_us_sleep(10); continue; }
        uint8_t* out = rte_pktmbuf_mtod(m, uint8_t*);
        const uint16_t max = rte_pktmbuf_tailroom(m);
        uint16_t pos = 0; uint64_t eff_this=0;

        if(cfg.vstream && !sent_init){
            if(max < sizeof(PfsXdpFrameHdr)){ rte_pktmbuf_free(m); c_tailroom_skip++; continue; }
            PfsXdpFrameHdr h={0}; h.magic=0x50565358u; h.version=2; h.flags=(uint16_t)((cfg.arith?1:0) | (1u<<2)); h.seq=seq++; h.desc_count=0; h.reserved=0;
            memcpy(out, &h, sizeof(h)); pos += (uint16_t)sizeof(h);
            m->data_len = m->pkt_len = pos;
            int pid = cfg.ports[rr_port]; uint16_t qid = (uint16_t)rr_q;
            uint16_t nb = rte_eth_tx_burst(pid, qid, &m, 1);
            if(nb==0){ c_tx_zero++; rte_pktmbuf_free(m); } else { sent_frames++; }
            sent_init = 1;
            if(++rr_q >= cfg.tx_queues){ rr_q = 0; rr_port = (rr_port + 1) % cfg.n_ports; }
            continue;
        }

        if(cfg.vstream){
            uint32_t dpf = cfg.desc_per_frame; if(dpf==0) dpf=64;
            uint32_t align = cfg.align? cfg.align : 1; uint32_t shift=0; while(((1u<<shift) < align) && shift<31) shift++;
            static uint32_t rr=0; uint32_t sid = rr++ % cfg.streams;
            size_t hdr_pos = 0;
            enum { MAXP = 1024 };
            uint64_t off_buf[MAXP];
            uint32_t len_buf[MAXP];
            uint32_t pcnt = 0;
            // optional Ethernet header for AF_PACKET
            if(cfg.eth_hdr){
                if(max - pos < sizeof(struct rte_ether_hdr)){ rte_pktmbuf_free(m); c_tailroom_skip++; continue; }
                struct rte_ether_hdr *eh = (struct rte_ether_hdr*)(out + pos);
                memset(eh->dst_addr.addr_bytes, 0xFF, RTE_ETHER_ADDR_LEN);
                struct rte_ether_addr mac; memset(&mac,0,sizeof(mac)); rte_eth_macaddr_get(cfg.ports[rr_port], &mac); rte_ether_addr_copy(&mac, &eh->src_addr);
                eh->ether_type = rte_cpu_to_be_16(0x88B5);
                pos += sizeof(struct rte_ether_hdr);
            }
            // protocol header (optional)
            if(cfg.proto_hdr){
                if(max - pos < sizeof(PfsVarintHdr)){ rte_pktmbuf_free(m); c_tailroom_skip++; continue; }
                PfsVarintHdr vh; vh.magic=0x50565254u; vh.version=1; vh.align_shift=(uint8_t)shift; vh.payload_len=0; vh.flags=0; vh.rsvd=0;
                hdr_pos = pos;
                memcpy(out+pos, &vh, sizeof(vh)); pos += (uint16_t)sizeof(vh);
            }
            // stream id
            size_t wrote = uvarint_enc(out+pos, max-pos, (uint64_t)sid); if(!wrote){ c_encode_fail++; rte_pktmbuf_free(m); continue; } pos += (uint16_t)wrote;
            uint64_t base = blob.size/2; uint64_t prev_off = prev_off_by_stream[sid]; const uint32_t merge_gap=64;
            for(uint32_t i=0;i<dpf && pcnt<MAXP;i++){
                x = xorshift64(x);
                uint32_t len = (uint32_t)((x % (align ? (align*4):4096)) + align); if(len>262144u) len=262144u; if(align>1){ len &= ~(align-1u); if(len<align) len=align; }
                uint64_t off = (x % (blob.size?blob.size:1)); if(align>1) off &= ~((uint64_t)align-1ULL);
                if(off + len > blob.size){ if(len > blob.size) len=(uint32_t)blob.size; off = blob.size - len; if(align>1) off &= ~((uint64_t)align-1ULL); }
                if(pcnt>0){ uint64_t last_off = off_buf[pcnt-1]; uint64_t last_len = len_buf[pcnt-1]; if(off <= last_off + last_len + merge_gap){ uint64_t new_end = off + len; uint64_t last_end = last_off + last_len; if(new_end>last_end){ len_buf[pcnt-1] = (uint32_t)(new_end - last_off); } continue; } }
                off_buf[pcnt]=off; len_buf[pcnt]=len; pcnt++;
            }
            for(uint32_t i=0;i<pcnt;i++){
                uint64_t off = off_buf[i]; uint32_t len = len_buf[i];
                int64_t delta = (prev_off == 0 && i==0) ? (int64_t)(off - base) : (int64_t)(off - prev_off);
                uint64_t zz = zz_enc64(delta);
                wrote = uvarint_enc(out+pos, max-pos, zz); if(!wrote){ c_encode_fail++; break; } pos += (uint16_t)wrote;
                uint64_t Lq = (uint64_t)(len >> shift);
                wrote = uvarint_enc(out+pos, max-pos, Lq); if(!wrote){ c_encode_fail++; break; } pos += (uint16_t)wrote;
                prev_off = off; eff_this += len;
                if(pos + 8 >= max) break;
            }
            // backfill payload_len if proto header used
            if(cfg.proto_hdr){
                size_t after_hdr = hdr_pos + sizeof(PfsVarintHdr);
                uint16_t payload_len = (uint16_t)((pos > after_hdr) ? (pos - after_hdr) : 0);
                ((PfsVarintHdr*)(out + hdr_pos))->payload_len = payload_len;
            }
            uint64_t h = 1469598103934665603ULL; size_t readpos = 0; uint64_t off_acc = prev_off_by_stream[sid] ? prev_off_by_stream[sid] : base; int first = prev_off_by_stream[sid] ? 0 : 1;
            { // skip sid
                size_t ioff=0; while(ioff<pos){ uint8_t b = out[ioff++]; if(!(b & 0x80)) break; } readpos = ioff; }
            while(readpos + 8 <= pos){
                uint64_t u=0; int sh=0; while(readpos < pos){ uint8_t b=out[readpos++]; u |= ((uint64_t)(b & 0x7F)) << sh; if(!(b & 0x80)) break; sh += 7; }
                uint64_t Lu=0; sh=0; while(readpos < pos){ uint8_t b=out[readpos++]; Lu |= ((uint64_t)(b & 0x7F)) << sh; if(!(b & 0x80)) break; sh += 7; }
                uint64_t L = Lu << shift;
                int64_t d = (int64_t)((u >> 1) ^ (~(u & 1) + 1));
                off_acc = first ? (base + d) : (off_acc + d); first = 0;
                if(off_acc + L <= blob.size){ const uint8_t* pdat = (const uint8_t*)blob.addr + off_acc; for(uint64_t k=0;k<L;k++){ h ^= pdat[k]; h *= 1099511628211ULL; } }
            }
            if(pos + 8 <= max){ memcpy(out+pos, &h, 8); pos += 8; }

            if(rte_pktmbuf_append(m, pos)==NULL){ c_append_fail++; rte_pktmbuf_free(m); continue; }
            int pid = cfg.ports[rr_port]; uint16_t qid = (uint16_t)rr_q;
            uint16_t nb = rte_eth_tx_burst(pid, qid, &m, 1);
            if(nb==0){ c_tx_zero++; rte_pktmbuf_free(m); } else { sent_frames++; bytes_eff += eff_this; desc_bytes_sum += pos; prev_off_by_stream[sid] = prev_off; }
            if(++rr_q >= cfg.tx_queues){ rr_q = 0; rr_port = (rr_port + 1) % cfg.n_ports; }
        } else {
            if(max < sizeof(PfsXdpFrameHdr)){ rte_pktmbuf_free(m); c_tailroom_skip++; continue; }
            PfsXdpFrameHdr h={0}; h.magic=0x50565358u; h.version=1; h.flags=(uint16_t)(cfg.arith?1:0); h.seq=seq++; h.desc_count=0; h.reserved=0;
            memcpy(out, &h, sizeof(h)); pos += (uint16_t)sizeof(h);
            if(rte_pktmbuf_append(m, pos)==NULL){ rte_pktmbuf_free(m); continue; }
            int pid = cfg.ports[rr_port]; uint16_t qid = (uint16_t)rr_q;
            uint16_t nb = rte_eth_tx_burst(pid, qid, &m, 1);
            if(nb==0){ c_tx_zero++; rte_pktmbuf_free(m); } else { sent_frames++; }
            if(++rr_q >= cfg.tx_queues){ rr_q = 0; rr_port = (rr_port + 1) % cfg.n_ports; }
        }

        double tn=now_sec(); if(cfg.verbose && (tn - tlast) >= 0.5){ double mb = bytes_eff/1e6; double mbps = mb/(tn - t0); fprintf(stderr,"[TX-DPDK] eff=%.1f MB avg=%.1f MB/s frames=%" PRIu64 "\n", mb, mbps, sent_frames); tlast=tn; }
    }

    double t1=now_sec(); double mb = bytes_eff/1e6; double mbps = mb/(t1 - t0 + 1e-9);
    if(cfg.vstream){ double db = desc_bytes_sum/1e6; double ratio = desc_bytes_sum? ((double)desc_bytes_sum / (double)bytes_eff) : 0.0; fprintf(stderr,"[TX-DPDK DONE] eff_bytes=%" PRIu64 " (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames=%" PRIu64 " desc_bytes=%" PRIu64 " (%.3f MB) desc_ratio=%.6f\n", bytes_eff, mb, (t1-t0), mbps, sent_frames, desc_bytes_sum, db, ratio); }
    else { fprintf(stderr,"[TX-DPDK DONE] eff_bytes=%" PRIu64 " (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames=%" PRIu64 "\n", bytes_eff, mb, (t1-t0), mbps, sent_frames); }
    fprintf(stderr, "[TX-DPDK STATS] alloc_fail=%" PRIu64 " append_fail=%" PRIu64 " tx_zero=%" PRIu64 " encode_fail=%" PRIu64 " tailroom_skip=%" PRIu64 "\n", c_alloc_fail, c_append_fail, c_tx_zero, c_encode_fail, c_tailroom_skip);

    for(int i=0;i<cfg.n_ports;i++){ rte_eth_dev_stop(cfg.ports[i]); rte_eth_dev_close(cfg.ports[i]); }
    pfs_hugeblob_unmap(&blob);
    return 0;
}

