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
#include <rte_mbuf.h>
#include <rte_mempool.h>
#include <rte_lcore.h>
#include <rte_cycles.h>
#include <sys/wait.h>
#include <ctype.h>

// PacketFS
#include "../memory/pfs_hugeblob.h"
#include "../gram/pfs_gram.h"
#include "../pcpu/pfs_pcpu.h"

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void die(const char* fmt, ...){ va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);} 

// varint helpers
static inline uint64_t zz_dec64(uint64_t u){ return (int64_t)((u >> 1) ^ (~(u & 1) + 1)); }
static inline size_t uvarint_dec(const uint8_t* in, size_t max, uint64_t* out){ uint64_t v=0; int shift=0; size_t i=0; while(i<max){ uint8_t b=in[i++]; v |= ((uint64_t)(b & 0x7F)) << shift; if(!(b & 0x80)){ *out=v; return i; } shift += 7; if(shift>63) break; } return 0; }

typedef struct {
    int ports[32];          // list of port ids
    int n_ports;            // number of active ports
    const char* ports_csv;  // CSV of port ids
    const char* pcis_csv;   // CSV of PCI names
    int rx_queues;          // queues per port (single-core RR)

    const char* eal;        // EAL args
    size_t blob_size;
    const char* huge_dir;
    const char* blob_name;
    int verbose;
    // pCPU
    int pcpu_enable;
    pfs_pcpu_op_t pcpu_op;
    uint8_t pcpu_imm;
    int l2_skip;            // bytes to skip before varint payload (e.g., 14 for Ethernet)
} RxConfig;

static void build_eal_argv(const char* eal_str, int* out_argc, char*** out_argv){
    const char* def = "-l 1 -n 4"; // avoid core 0 if TX uses it
    const char* s = (eal_str && *eal_str) ? eal_str : def;
    int count = 1; for(const char* p=s; *p; p++){ if(*p==' ') count++; }
    char** av = (char**)calloc((size_t)count+2, sizeof(char*)); int ac=0;
    av[ac++] = strdup("pfs_dpdk_rx");
    char* tmp = strdup(s); char* save=NULL; char* tok=strtok_r(tmp, " ", &save);
    while(tok){ av[ac++] = strdup(tok); tok=strtok_r(NULL, " ", &save);} av[ac]=NULL; *out_argc=ac; *out_argv=av; free(tmp);
}

// Simple varint streaming parser with trailing 8-byte hash (FNV-1a)
static inline uint64_t fnv1a64_init(void){ return 1469598103934665603ULL; }
static inline uint64_t fnv1a64_update(uint64_t h, const void* data, size_t n){ const uint8_t* p=(const uint8_t*)data; for(size_t i=0;i<n;i++){ h ^= p[i]; h *= 1099511628211ULL; } return h; }

static int parse_cpu_baseline_mb(const char* line, double* out_mb){
    // Expect line like: CPU_BASELINE size=... ns=... MBps=...
    const char* p = strstr(line, "MBps=");
    if(!p) return -1;
    p += 5; // skip MBps=
    char* end=NULL; double v = strtod(p, &end);
    if(end==p) return -1; *out_mb = v; return 0;
}

static int run_cpu_baseline(uint64_t size_bytes, const char* op, int imm, double* out_mb){
    // Determine baseline binary path
    const char* exe = getenv("PFS_CPU_BASELINE");
    if(!exe || !*exe) exe = "dev/wip/native/pfs_cpu_baseline";
    char cmd[512];
    snprintf(cmd, sizeof(cmd), "%s --size-bytes %" PRIu64 " --op %s --imm %d 2>/dev/null", exe, size_bytes, op, imm);
    FILE* fp = popen(cmd, "r"); if(!fp) return -1;
    char buf[256]; double mb=0.0; int ok= -1;
    while(fgets(buf, sizeof(buf), fp)){
        if(strncmp(buf, "CPU_BASELINE", 12)==0){ if(parse_cpu_baseline_mb(buf, &mb)==0){ ok=0; break; } }
    }
    int rc = pclose(fp); (void)rc; if(ok==0){ *out_mb = mb; return 0; } return -1;
}

int main(int argc, char** argv){
    signal(SIGINT, on_sigint);
    RxConfig cfg; memset(&cfg,0,sizeof(cfg)); cfg.n_ports=0; cfg.ports_csv=NULL; cfg.pcis_csv=NULL; cfg.rx_queues=1; cfg.eal=NULL; cfg.blob_size=2ULL<<30; cfg.huge_dir="/dev/hugepages"; cfg.blob_name="pfs_stream_blob"; cfg.verbose=1;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--port") && i+1<argc){ cfg.ports[0] = (int)strtol(argv[++i],NULL,10); cfg.n_ports=1; }
        else if(!strcmp(argv[i],"--ports") && i+1<argc) cfg.ports_csv = argv[++i];
        else if(!strcmp(argv[i],"--pcis") && i+1<argc) cfg.pcis_csv = argv[++i];
        else if(!strcmp(argv[i],"--rx-queues") && i+1<argc) cfg.rx_queues = (int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--eal") && i+1<argc) cfg.eal = argv[++i];
        else if(!strcmp(argv[i],"--blob-size") && i+1<argc) cfg.blob_size = strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) cfg.huge_dir = argv[++i];
        else if(!strcmp(argv[i],"--blob-name") && i+1<argc) cfg.blob_name = argv[++i];
        else if(!strcmp(argv[i],"--pcpu") && i+1<argc) cfg.pcpu_enable = (int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--pcpu-op") && i+1<argc){ const char* o=argv[++i]; if(!strcmp(o,"fnv")||!strcmp(o,"fnv64")) cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_FNV64; else if(!strcmp(o,"xor")) cfg.pcpu_op=PFS_PCPU_OP_XOR_IMM8; else if(!strcmp(o,"add")) cfg.pcpu_op=PFS_PCPU_OP_ADD_IMM8; else if(!strcmp(o,"crc32c")) cfg.pcpu_op=PFS_PCPU_OP_CHECKSUM_CRC32C; else if(!strcmp(o,"counteq")) cfg.pcpu_op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
        else if(!strcmp(argv[i],"--imm") && i+1<argc) cfg.pcpu_imm=(uint8_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--l2-skip") && i+1<argc) cfg.l2_skip=(int)strtol(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--quiet")) cfg.verbose=0;
        else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")){
            printf("Usage: %s [--ports CSV | --pcis CSV | --port N] [--rx-queues N] [--eal \"-l 1 -n 4\"] [--blob-size B] [--pcpu 0|1] [--pcpu-op fnv|xor|add] [--imm N]\n", argv[0]);
            return 0;
        }
    }

    // Map blob
    PfsHugeBlob blob; if(pfs_hugeblob_map(cfg.blob_size, cfg.huge_dir, cfg.blob_name, &blob)!=0) die("map blob: %s", strerror(errno)); pfs_hugeblob_set_keep(&blob,1);

    int eal_argc=0; char** eal_argv=NULL; build_eal_argv(cfg.eal, &eal_argc, &eal_argv);
    int ret = rte_eal_init(eal_argc, eal_argv);
    if(ret < 0){ die("rte_eal_init failed; ensure hugepages configured (try: just hugepages-status)"); }

    // Resolve ports by csv
    if(cfg.pcis_csv && *cfg.pcis_csv){ char* tmp=strdup(cfg.pcis_csv); char* save=NULL; char* tok=strtok_r(tmp, ",", &save); while(tok && cfg.n_ports < (int)(sizeof(cfg.ports)/sizeof(cfg.ports[0]))){ uint16_t pid16=0; if(rte_eth_dev_get_port_by_name(tok,&pid16)==0 && rte_eth_dev_is_valid_port(pid16)) cfg.ports[cfg.n_ports++]=(int)pid16; tok=strtok_r(NULL, ",", &save);} free(tmp); }
    if(cfg.ports_csv && *cfg.ports_csv){ char* tmp=strdup(cfg.ports_csv); char* save=NULL; char* tok=strtok_r(tmp, ",", &save); while(tok && cfg.n_ports < (int)(sizeof(cfg.ports)/sizeof(cfg.ports[0]))){ int pid=(int)strtol(tok,NULL,10); if(rte_eth_dev_is_valid_port(pid)) cfg.ports[cfg.n_ports++]=pid; tok=strtok_r(NULL, ",", &save);} free(tmp); }
    if(cfg.n_ports==0){ if(rte_eth_dev_is_valid_port(0)){ cfg.ports[0]=0; cfg.n_ports=1; } else die("no valid DPDK ports available"); }
    if(cfg.rx_queues<=0) cfg.rx_queues=1;

    if(cfg.verbose){ fprintf(stderr, "[RX-DPDK] ports="); for(int i=0;i<cfg.n_ports;i++){ fprintf(stderr, "%s%d", (i?",":""), cfg.ports[i]); } fprintf(stderr, " rxq=%d eal=\"%s\" blob=%zu dir=%s name=%s pcpu=%d op=%d imm=%u l2_skip=%d\n", cfg.rx_queues, cfg.eal?cfg.eal:"-l 1 -n 4", (size_t)cfg.blob_size, cfg.huge_dir, cfg.blob_name, cfg.pcpu_enable, (int)cfg.pcpu_op, (unsigned)cfg.pcpu_imm, cfg.l2_skip); }

    // Create mempool
    struct rte_mempool* mp = rte_pktmbuf_pool_create("pfs_dpdk_rx_pool", 8192*4 * (unsigned)cfg.n_ports, 512, 0, RTE_MBUF_DEFAULT_BUF_SIZE, rte_socket_id());
    if(!mp) die("mbuf pool create failed: %s", rte_strerror(rte_errno));

    struct rte_eth_conf port_conf; memset(&port_conf,0,sizeof(port_conf));
    port_conf.rxmode.mq_mode = RTE_ETH_MQ_RX_NONE;
    port_conf.txmode.mq_mode = RTE_ETH_MQ_TX_NONE;
    for(int i=0;i<cfg.n_ports;i++){
        int pid = cfg.ports[i];
        // Some PMDs (e.g., r8169) require at least one TX queue even in RX-only to avoid crashes in dev_start.
        int txq_min = 1;
        if(rte_eth_dev_configure(pid, cfg.rx_queues, txq_min, &port_conf) < 0) die("rte_eth_dev_configure port %d", pid);
        for(int q=0;q<cfg.rx_queues;q++){
            if(rte_eth_rx_queue_setup(pid, q, 1024, rte_eth_dev_socket_id(pid), NULL, mp) < 0) die("rx_queue_setup port %d q%d", pid, q);
        }
        // Minimal TX queue to satisfy PMD requirements; we will not transmit from RX tool.
        if(rte_eth_tx_queue_setup(pid, 0, 1024, rte_eth_dev_socket_id(pid), NULL) < 0) die("tx_queue_setup port %d q0", pid);
        if(rte_eth_dev_start(pid) < 0) die("rte_eth_dev_start port %d", pid);
    }

    // Stats
    uint64_t bytes_eff=0, frames=0, desc_bytes_sum=0; double t0=now_sec(), tlast=t0; uint64_t csum = fnv1a64_init();
    uint64_t c_sid_fail=0, c_pair_fail=0, c_oob=0;
    uint64_t last_off_by_stream[256]; memset(last_off_by_stream, 0, sizeof(last_off_by_stream));
    pfs_pcpu_metrics_t pcpu_m; memset(&pcpu_m,0,sizeof(pcpu_m));

    // Single-core async polling across ports & queues
    struct rte_mbuf* bufs[64]; int rr_port=0; int rr_q=0;
    while(!g_stop){
        int pid = cfg.ports[rr_port]; uint16_t qid = (uint16_t)rr_q;
        uint16_t nb = rte_eth_rx_burst(pid, qid, bufs, 64);
        if(nb==0){ // progress RR and nap a bit
            if(++rr_q >= cfg.rx_queues){ rr_q = 0; rr_port = (rr_port + 1) % cfg.n_ports; }
            rte_delay_us_sleep(50);
            continue;
        }
        for(uint16_t i=0;i<nb;i++){
            struct rte_mbuf* m = bufs[i];
            const uint8_t* p = rte_pktmbuf_mtod(m, const uint8_t*);
            uint16_t plen = rte_pktmbuf_pkt_len(m);
            if(plen < 8){ rte_pktmbuf_free(m); continue; }
            size_t pos = (cfg.l2_skip>0 && (size_t)cfg.l2_skip < plen)? (size_t)cfg.l2_skip : 0;
            // Optional protocol header detection
            uint16_t varint_len = 0; uint8_t align_shift = 0; size_t after_hdr = 0; size_t varint_end = 0;
            if(plen - pos >= (sizeof(uint32_t) + 6)){
                const uint32_t* mg = (const uint32_t*)(p + pos);
                if(*mg == 0x50565254u){
                    // PVRT header
                    pos += sizeof(uint32_t); // magic
                    uint8_t version = p[pos++]; align_shift = p[pos++];
                    varint_len = *(const uint16_t*)(p + pos); pos += sizeof(uint16_t);
                    uint8_t flags = p[pos++]; uint8_t rsvd = p[pos++]; (void)flags; (void)rsvd; (void)version;
                    after_hdr = pos;
                    varint_end = after_hdr + (size_t)varint_len;
                    size_t max_end = (size_t)((plen >= 8) ? (plen - 8) : 0);
                    if(varint_end > max_end) varint_end = max_end;
                }
            }
            // If operating with L2 skip, require PVRT header to avoid parsing non-our frames
            if(cfg.l2_skip > 0 && varint_end == 0){ rte_pktmbuf_free(m); continue; }
            size_t sid_max = varint_end ? (varint_end - pos) : (size_t)((plen > 8 && pos < plen-8) ? (plen - 8 - pos) : 0);
            uint64_t sid=0; size_t m0 = uvarint_dec(p+pos, sid_max, &sid); if(!m0){ rte_pktmbuf_free(m); continue; } pos += m0; sid &= 0xFF;
            uint64_t base = blob.size/2; uint64_t off_acc = last_off_by_stream[sid] ? last_off_by_stream[sid] : base; int first = last_off_by_stream[sid] ? 0 : 1;
            uint64_t eff=0;
            PfsGramDesc descs[1024]; size_t dcnt=0;
            size_t parse_limit = varint_end ? varint_end : (size_t)((plen >= 8) ? (plen - 8) : 0);
            while(pos + 8 <= plen && pos < parse_limit){
                uint64_t u; size_t m1 = uvarint_dec(p+pos, (size_t)(parse_limit - pos), &u); if(!m1){ c_pair_fail++; break; } pos += m1;
                uint64_t Lu; size_t m2 = uvarint_dec(p+pos, (size_t)(parse_limit - pos), &Lu); if(!m2){ c_pair_fail++; break; } pos += m2;
                int64_t delta = (int64_t)zz_dec64(u);
                uint64_t L = align_shift? (Lu << align_shift) : Lu;
                off_acc = first ? (base + delta) : (off_acc + delta); first=0;
                if(off_acc + L <= blob.size){ csum = fnv1a64_update(csum, (uint8_t*)blob.addr + off_acc, (size_t)L); bytes_eff += L; eff += L; if(cfg.pcpu_enable && dcnt<1024){ descs[dcnt].offset=off_acc; descs[dcnt].len=(uint32_t)L; descs[dcnt].flags=0; dcnt++; } } else { c_oob++; }
            }
            if(cfg.pcpu_enable && dcnt){ pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); (void)pfs_pcpu_apply(blob.addr, blob.size, descs, dcnt, cfg.pcpu_op, cfg.pcpu_imm, 1469598103934665603ULL, &mm); pcpu_m.bytes_total+=mm.bytes_total; pcpu_m.bytes_touched+=mm.bytes_touched; pcpu_m.desc_count+=mm.desc_count; pcpu_m.ns+=mm.ns; pcpu_m.checksum_out^=mm.checksum_out; }
            last_off_by_stream[sid] = off_acc;
            desc_bytes_sum += plen; frames++;
            rte_pktmbuf_free(m);
        }
        if(++rr_q >= cfg.rx_queues){ rr_q = 0; rr_port = (rr_port + 1) % cfg.n_ports; }
        double tn=now_sec(); if(cfg.verbose && (tn - tlast) >= 0.5){ double mb = bytes_eff/1e6; double mbps = mb/(tn - t0); fprintf(stderr,"[RX-DPDK] eff=%.1f MB avg=%.1f MB/s frames=%" PRIu64 "\n", mb, mbps, frames); tlast=tn; }
    }

    double t1=now_sec(); double eff_mb = bytes_eff/1e6; double eff_mbps = eff_mb/(t1 - t0 + 1e-9);
    double db = desc_bytes_sum/1e6; double ratio = desc_bytes_sum? ((double)desc_bytes_sum / (double)bytes_eff) : 0.0;
    fprintf(stderr,"[RX-DPDK DONE] eff_bytes=%" PRIu64 " (%.1f MB) elapsed=%.3f s avg=%.1f MB/s checksum=0x%016" PRIx64 " frames=%" PRIu64 " desc_bytes=%" PRIu64 " (%.3f MB) desc_ratio=%.6f\n",
        bytes_eff, eff_mb, (t1-t0), eff_mbps, csum, frames, desc_bytes_sum, db, ratio);
    fprintf(stderr, "[RX-DPDK STATS] sid_fail=%" PRIu64 " pair_fail=%" PRIu64 " oob=%" PRIu64 "\n", c_sid_fail, c_pair_fail, c_oob);
    if(cfg.pcpu_enable){
        double pc_mb = pcpu_m.bytes_touched/1e6; double pc_mbps = (t1>t0)? (pc_mb/((t1-t0))) : 0.0;
        // Map pCPU op to baseline op string
        const char* bop = "checksum";
        if(cfg.pcpu_op == PFS_PCPU_OP_XOR_IMM8) bop = "xor8";
        else if(cfg.pcpu_op == PFS_PCPU_OP_ADD_IMM8) bop = "add8";
        else bop = "checksum"; // fnv/crc32c -> checksum baseline
        double cpu_mbps = 0.0; int bl_rc = run_cpu_baseline(pcpu_m.bytes_touched, bop, (int)cfg.pcpu_imm, &cpu_mbps);
        double pwn_exec_tp = (cpu_mbps > 0.0) ? (pc_mbps / cpu_mbps) : 0.0;           // throughput ratio (exec)
        double pwn_eff_tp  = (cpu_mbps > 0.0) ? (eff_mbps / cpu_mbps) : 0.0;          // throughput ratio (effective)
        double pwn_exec_t  = (cpu_mbps > 0.0 && pc_mb > 0.0) ? ((t1-t0) / (pc_mb / cpu_mbps)) : 0.0; // time ratio PFS/CPU for exec bytes
        double pwn_eff_t   = (cpu_mbps > 0.0 && eff_mb > 0.0) ? ((t1-t0) / (eff_mb / cpu_mbps)) : 0.0; // time ratio PFS/CPU for effective bytes
        fprintf(stderr, "[RX-DPDK PCPU] touched=%.3f MB desc=%" PRIu64 " time=%.3f s pcpu_MBps=%.1f eff_MBps=%.1f op=%d imm=%u\n",
                pc_mb, pcpu_m.desc_count, (double)pcpu_m.ns/1e9, pc_mbps, eff_mbps, (int)cfg.pcpu_op, (unsigned)cfg.pcpu_imm);
        if(bl_rc==0){
            fprintf(stderr, "[RX-DPDK PCPU] baseline_MBps=%.3f pwnCPU_exec_tp=%.6f pwnCPU_eff_tp=%.6f pwnCPU_exec_t=%.6f pwnCPU_eff_t=%.6f\n",
                    cpu_mbps, pwn_exec_tp, pwn_eff_tp, pwn_exec_t, pwn_eff_t);
        } else {
            fprintf(stderr, "[RX-DPDK PCPU] baseline unavailable (set PFS_CPU_BASELINE to path or build dev/wip/native/pfs_cpu_baseline)\n");
        }
    }

    for(int i=0;i<cfg.n_ports;i++){ rte_eth_dev_stop(cfg.ports[i]); rte_eth_dev_close(cfg.ports[i]); }
    pfs_hugeblob_unmap(&blob);
    return 0;
}

