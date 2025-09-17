// SPDX-License-Identifier: MIT
// Single-threaded AF_PACKET (TPACKET_V3) RX harness with hugepage-backed user ring
// - Captures packets into a kernel ring (TPACKET_V3)
// - Copies payloads into a massive user-space ring in a hugepage blob (GPU-friendly)
// - Optional pCPU program parsing (wired for future use)
// - Stats printed periodically and on exit

#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include <sys/stat.h>
#include <pwd.h>
#include <sys/utsname.h>

#include "../../../realsrc/packetfs/uapi/pfs_ringpeek.h"
#include <sys/utsname.h>
#include <pwd.h>

#include "../../../realsrc/packetfs/memory/pfs_hugeblob.h"
#include "../../../realsrc/packetfs/pcpu/pfs_pcpu.h"

#ifndef TP_FT_REQ_FILL_RXHASH
#define TP_FT_REQ_FILL_RXHASH 0x1
#endif

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop = 1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

typedef struct {
    const char* ifname;    // single-interface shortcut
    const char* ifaces;    // comma-separated list (overrides ifname if provided)
    size_t ring_mem;       // bytes for kernel ring mapping (approx)
    uint32_t frame_size;   // kernel ring frame size (e.g., 2048)
    uint32_t block_size;   // kernel ring block size (e.g., 1<<20)
    uint32_t timeout_ms;   // retire block timeout
    uint32_t snaplen;      // copy up to this many bytes per packet into user ring
    const char* huge_dir;  // hugepage mount
    const char* blob_name; // blob name
    size_t blob_size;      // huge blob size in bytes
    uint32_t align;        // alignment for user ring copies
    double duration_s;     // stop after duration (<=0 means until Ctrl-C)
    int verbose;
    // pCPU (optional)
    int pcpu_enable;
    const char* prog;      // op chain string e.g. "counteq:0,crc32c"
    int pcpu_metrics;      // print pCPU bytes_touched per interval
    // PACKET_FANOUT (single thread multi-queue/ports)
    int fanout_id;
    int fanout_mode; // 0=none, 1=hash, 2=lb
    // Optimizer
    int auto_tune;         // heuristic geometry tuning before ring setup
    int llvm_opt;          // enable LLVM-inspired optimizer hints (no real JIT yet)
    const char* llvm_hint; // optional hint string (e.g., compute/matrix, network/crc)
    // MMIO peek via pfs_ringpeek
    int peek_mmio;
    const char* peek_bdf; // optional (module may auto-detect)
    char mmio_out_path[256];
    // Plan file output path
    const char* plan_out;
    // Run identification and pinning capture
    char run_id[64];
    char cpu_list[256];
} Cfg;

// Simple metadata slot for stored packets (GPU-friendly placeholder)
typedef struct {
    uint64_t off;     // offset into huge blob
    uint32_t len;     // captured length
    uint32_t rxhash;  // kernel-provided RX hash (optional)
} PacketMeta;

// Kernel ring mapping
typedef struct {
    int fd;
    void* map;
    size_t map_len;
    struct tpacket_req3 req;
} KRing;

static int setup_kernel_ring(const Cfg* cfg, KRing* kr)
{
    memset(kr, 0, sizeof(*kr));
    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if(fd < 0){ perror("socket(AF_PACKET)"); return -1; }

    int version = TPACKET_V3;
    if(setsockopt(fd, SOL_PACKET, PACKET_VERSION, &version, sizeof(version)) != 0){ perror("setsockopt PACKET_VERSION TPACKET_V3"); close(fd); return -1; }

    // Compute ring geometry
    uint32_t frame_sz = cfg->frame_size ? cfg->frame_size : 2048;
    uint32_t blk_sz = cfg->block_size ? cfg->block_size : (1u<<20);
    if(cfg->auto_tune){
        // Heuristic tuning: keep frame >= snaplen rounded to next power-of-two up to 4096
        uint32_t target = cfg->snaplen ? cfg->snaplen : 2048;
        if(target < 256) target = 256; if(target > 4096) target = 4096;
        // round up to nearest 512
        uint32_t r = (target + 511) & ~511u;
        if(r > frame_sz) frame_sz = r;
        // Align write alignment to 64 or 256 depending on snaplen
        (void)0;
    }
    if(blk_sz % getpagesize() != 0){ blk_sz = (blk_sz / getpagesize()) * getpagesize(); if(blk_sz < (1u<<16)) blk_sz = (1u<<16); }
    if(blk_sz < frame_sz) blk_sz = frame_sz * 8; // ensure multiple frames per block

    uint32_t frames_per_block = blk_sz / frame_sz;
    if(frames_per_block == 0) frames_per_block = 1;

    uint32_t block_nr = (uint32_t)(cfg->ring_mem / blk_sz);
    if(block_nr == 0) block_nr = 1;

    uint32_t frame_nr = frames_per_block * block_nr;

    struct tpacket_req3 req;
    memset(&req, 0, sizeof(req));
    req.tp_block_size = blk_sz;
    req.tp_frame_size = frame_sz;
    req.tp_block_nr = block_nr;
    req.tp_frame_nr = frame_nr;
    req.tp_retire_blk_tov = cfg->timeout_ms ? cfg->timeout_ms : 100; // ms
    req.tp_sizeof_priv = 0;
    req.tp_feature_req_word = TP_FT_REQ_FILL_RXHASH;

    if(setsockopt(fd, SOL_PACKET, PACKET_RX_RING, &req, sizeof(req)) != 0){ perror("setsockopt PACKET_RX_RING (TPACKET_V3)"); close(fd); return -1; }

    size_t map_len = (size_t)req.tp_block_size * req.tp_block_nr;
    void* mp = mmap(NULL, map_len, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_LOCKED, fd, 0);
    if(mp == MAP_FAILED){ perror("mmap PACKET_RX_RING"); close(fd); return -1; }

    // Bind to interface
    struct ifreq ifr; memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, cfg->ifname, sizeof(ifr.ifr_name)-1);
    if(ioctl(fd, SIOCGIFINDEX, &ifr) != 0){ perror("ioctl SIOCGIFINDEX"); munmap(mp, map_len); close(fd); return -1; }

    struct sockaddr_ll sll = {0};
    sll.sll_family = AF_PACKET;
    sll.sll_ifindex = ifr.ifr_ifindex;
    sll.sll_protocol = htons(ETH_P_ALL);
    if(bind(fd, (struct sockaddr*)&sll, sizeof(sll)) != 0){ perror("bind(AF_PACKET)"); munmap(mp, map_len); close(fd); return -1; }

    // Optional PACKET_FANOUT
    if(cfg->fanout_id > 0){
        int mode = 0;
        if(cfg->fanout_mode == 1) mode = PACKET_FANOUT_HASH;
        else if(cfg->fanout_mode == 2) mode = PACKET_FANOUT_LB;
        int fanout_arg = (cfg->fanout_id & 0xffff) | (mode << 16);
        if(setsockopt(fd, SOL_PACKET, PACKET_FANOUT, &fanout_arg, sizeof(fanout_arg)) != 0){
            perror("setsockopt PACKET_FANOUT"); /* non-fatal, continue */
        }
    }

    kr->fd = fd; kr->map = mp; kr->map_len = map_len; kr->req = req;
    return 0;
}

static void teardown_kernel_ring(KRing* kr)
{
    if(kr->map && kr->map_len) munmap(kr->map, kr->map_len);
    if(kr->fd >= 0) close(kr->fd);
    memset(kr, 0, sizeof(*kr));
}

static inline void cpu_relax(){ __asm__ __volatile__("pause" ::: "memory"); }

static void iso8601_utc(char* out, size_t n){
    time_t t = time(NULL); struct tm tmv; gmtime_r(&t, &tmv);
    strftime(out, n, "%Y-%m-%dT%H:%M:%SZ", &tmv);
}

static void read_cpu_list(char* out, size_t n){
    if(!out||n==0){return;} out[0]='\0';
    FILE* f = fopen("/proc/self/status", "r"); if(!f) return;
    char line[512];
    while(fgets(line, sizeof(line), f)){
        if(strncmp(line, "Cpus_allowed_list:", 19) == 0){
            const char* p = line + 19;
            while(*p==' '||*p=='\t') p++;
            size_t len = strcspn(p, "\n");
            if(len >= n) len = n-1;
            memcpy(out, p, len); out[len] = '\0';
            break;
        }
    }
    fclose(f);
}

static void hex_dump_line(FILE* f, uint64_t off, const unsigned char* p, size_t n){
    fprintf(f, "%08llx  ", (unsigned long long)off);
    for(size_t i=0;i<16;i++){
        if(i<n) fprintf(f, "%02x ", p[i]); else fprintf(f, "   ");
        if(i==7) fputc(' ', f);
    }
    fputc(' ', f);
    for(size_t i=0;i<16;i++){
        unsigned char c = (i<n)?p[i]:'.';
        fputc((c>=32 && c<127)?c:'.', f);
    }
    fputc('\n', f);
}

static void dump_window_to_file(int fd, FILE* f, uint32_t bar, uint64_t off, uint32_t len){
    struct pfs_ringpeek_window w; memset(&w,0,sizeof(w)); w.bar=bar; w.offset=off; w.length=len;
    if(ioctl(fd, PFS_RINGPEEK_IOC_SET_WINDOW, &w) != 0){ return; }
    unsigned char* buf = (unsigned char*)malloc(len); if(!buf){ return; }
    ssize_t r = read(fd, buf, len);
    if(r > 0){
        fprintf(f, "# BAR%u @ 0x%llx len=%u\n", bar, (unsigned long long)off, len);
        size_t pos=0; while(pos < (size_t)r){ size_t n = ((size_t)r - pos) > 16 ? 16 : ((size_t)r - pos); hex_dump_line(f, off+pos, buf+pos, n); pos += n; }
        fputc('\n', f);
    }
    free(buf);
}

static int mmio_peek_to_file(const Cfg* cfg, const char* out_path){
    int fd = open("/dev/pfs_ringpeek", O_RDONLY);
    if(fd < 0) return -1;
    // Ensure logs dir exists
    struct stat st; if(stat("logs", &st)!=0) mkdir("logs", 0755);
    FILE* f = fopen(out_path, "w"); if(!f){ close(fd); return -1; }

    // Dump a couple of useful windows on BAR4
    dump_window_to_file(fd, f, 4, 0x20, 64);   // TX base region (TNPDS)
    dump_window_to_file(fd, f, 4, 0xE0, 64);   // RX base region (RDSAR)
    // Also small headers
    dump_window_to_file(fd, f, 4, 0x00, 64);
    dump_window_to_file(fd, f, 4, 0x100, 64);

    fclose(f); close(fd);
    return 0;
}


static void write_plan_json(const Cfg* cfg, const char ifnames[][IFNAMSIZ], int ifn, KRing* rings, uint64_t blob_size){
    if(!cfg->plan_out || !*cfg->plan_out) return;
    FILE* pf = fopen(cfg->plan_out, "w");
    if(!pf){ perror("plan-out fopen"); return; }
    char ts[32]; iso8601_utc(ts, sizeof(ts));
    struct utsname uts; uname(&uts);
    char host[256]; if(gethostname(host, sizeof(host))!=0) strncpy(host, "unknown", sizeof(host));
    uid_t uid = getuid(); struct passwd* pw = getpwuid(uid);

    const char* fanout_str = (cfg->fanout_mode==1?"hash":(cfg->fanout_mode==2?"lb":"none"));

    // Optimizer rationale
    const char* rationale = "auto-selected by hint";
    if(cfg->llvm_hint){
        if(strstr(cfg->llvm_hint,"crc")) rationale = "CRC workload; align=64; snaplen>=512";
        else if(strstr(cfg->llvm_hint,"matrix")||strstr(cfg->llvm_hint,"hist")) rationale = "Histogram/matrix; align=64; snaplen>=1024";
    }

    // Use first ring geometry if available
    uint32_t frame_sz = (ifn>0)? rings[0].req.tp_frame_size : (cfg->frame_size?cfg->frame_size:2048);
    uint32_t block_sz = (ifn>0)? rings[0].req.tp_block_size : (cfg->block_size?cfg->block_size:(1u<<20));
    uint32_t frames_per_block = frame_sz? (block_sz / frame_sz) : 0;
    uint32_t block_nr = (ifn>0)? rings[0].req.tp_block_nr : (uint32_t)(cfg->ring_mem / (block_sz?block_sz:1));
    uint32_t frame_nr = frames_per_block * block_nr;

    fprintf(pf, "{\n");
    fprintf(pf, "  \"plan_version\": \"1.0.0\",\n");
    fprintf(pf, "  \"tool\": { \"name\": \"pfs_afpkt_rx\", \"version\": \"0.1.0\", \"git_rev\": \"\", \"binary_path\": \"bin/pfs_afpkt_rx\" },\n");
    fprintf(pf, "  \"run\": { \"run_id\": \"%s\", \"created_utc\": \"%s\", \"duration_requested_s\": %.3f, \"dry_run\": false },\n", cfg->run_id, ts, cfg->duration_s);
    fprintf(pf, "  \"environment\": { \"user\": \"%s\", \"host\": \"%s\", \"os\": \"%s\", \"kernel\": \"%s\", \"venv_path\": \"%s\", \"caps\": { \"cap_net_raw\": null }, \"inside_container\": false },\n",
            pw?pw->pw_name:"", host, uts.sysname, uts.release, "/home/punk/.venv");
    fprintf(pf, "  \"vcs\": { \"repo_root\": \"%s\", \"git_commit\": \"\", \"dirty\": null },\n", ".");
    fprintf(pf, "  \"mode\": \"af_packet\",\n");

    // Network interfaces
    fprintf(pf, "  \"network\": { \"interfaces\": [");
    for(int i=0;i<ifn;i++){
        struct ifreq ifr; memset(&ifr,0,sizeof(ifr)); strncpy(ifr.ifr_name, ifnames[i], IFNAMSIZ-1);
        int ifidx = -1; int tmpfd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
        if(tmpfd>=0){ if(ioctl(tmpfd, SIOCGIFINDEX, &ifr)==0) ifidx = ifr.ifr_ifindex; close(tmpfd);}        
        fprintf(pf, "%s{\"name\":\"%s\",\"ifindex\":%d,\"driver\":null,\"mtu\":null,\"mac\":null,\"pci_bdf\":null}",
                (i?",":""), ifnames[i], ifidx);
    }
    fprintf(pf, "], \"fanout\": { \"id\": %d, \"mode\": \"%s\" } },\n", cfg->fanout_id, fanout_str);

    fprintf(pf, "  \"kernel_ring\": { \"version\": \"TPACKET_V3\", \"frame_size\": %u, \"block_size\": %u, \"frames_per_block\": %u, \"block_nr\": %u, \"frame_nr\": %u, \"retire_blk_tov_ms\": %u },\n",
            frame_sz, block_sz, frames_per_block, block_nr, frame_nr, cfg->timeout_ms ? cfg->timeout_ms : 100);

    fprintf(pf, "  \"capture\": { \"snaplen\": %u, \"align\": %u, \"duration_s\": %.3f, \"store_payloads\": true, \"metadata_format_version\": 1 },\n",
            cfg->snaplen, cfg->align, cfg->duration_s);

    fprintf(pf, "  \"storage\": { \"huge_dir\": \"%s\", \"blob_name\": \"%s\", \"blob_size_bytes\": %zu, \"keep\": true },\n",
            cfg->huge_dir?cfg->huge_dir:"", cfg->blob_name?cfg->blob_name:"", (size_t)blob_size);

    fprintf(pf, "  \"optimizer\": { \"enabled\": %s, \"hint\": \"%s\", \"plan\": { \"op\": \"%s\", \"align\": %u, \"snaplen\": %u }, \"rationale\": \"%s\" },\n",
            cfg->llvm_opt?"true":"false", cfg->llvm_hint?cfg->llvm_hint:"",
            (cfg->prog?cfg->prog:""), cfg->align, cfg->snaplen, rationale);

    fprintf(pf, "  \"pcpu\": { \"enabled\": %s, \"program\": %s },\n",
            cfg->pcpu_enable?"true":"false", cfg->prog?"[\"single-op\"]":"[]");

    fprintf(pf, "  \"batching\": { \"prefetch_dist\": 2, \"copy_chunk_bytes\": 512 },\n");

    // pinning
    fprintf(pf, "  \"pinning\": { \"cpu_list\": \"%s\" },\n", cfg->cpu_list[0]?cfg->cpu_list:"");

    // outputs
    fprintf(pf, "  \"outputs\": { \"plan_path\": \"%s\", \"logs_dir\": \"logs/\", \"metrics_path\": \"logs/pfs_afpkt_rx_stats_%s.jsonl\"", cfg->plan_out, cfg->run_id);
    if(cfg->mmio_out_path[0]){
        fprintf(pf, ", \"debug\": { \"mmio\": [ \"%s\" ] }", cfg->mmio_out_path);
    }
    fprintf(pf, " },\n");

    fprintf(pf, "  \"metrics\": { \"interval_s\": 0.5, \"write_stats\": true, \"schema_version\": \"1.0.0\" },\n");
    fprintf(pf, "  \"security\": { \"sanitized\": true, \"secrets_in_env\": [], \"redactions\": {} },\n");
    fprintf(pf, "  \"notes\": [\"plan generated before capture\"],\n");
    fprintf(pf, "  \"errors\": []\n");
    fprintf(pf, "}\n");
    fclose(pf);
}

#define MAX_IFACES 16

int main(int argc, char** argv)
{
    signal(SIGINT, on_sigint);
    Cfg cfg = {0};
    cfg.ifname = "lo";
    cfg.ifaces = NULL;
    cfg.ring_mem = 64u<<20;  // 64 MiB default kernel ring
    cfg.frame_size = 2048;
    cfg.block_size = 1u<<20; // 1 MiB
    cfg.timeout_ms = 100;
    cfg.snaplen = 2048;
    cfg.huge_dir = "/mnt/huge1G";
    cfg.blob_name = "pfs_afpkt_blob";
    cfg.blob_size = 1ull<<30; // 1 GiB user ring by default
    cfg.align = 64;
    cfg.duration_s = 10.0;
    cfg.verbose = 1;
    cfg.pcpu_enable = 0;
    cfg.prog = NULL;
    cfg.pcpu_metrics = 0;
    cfg.fanout_id = 0;
    cfg.fanout_mode = 0;
    cfg.auto_tune = 1;
    cfg.llvm_opt = 0;
    cfg.llvm_hint = NULL;
    cfg.peek_mmio = 0;
    cfg.peek_bdf = NULL;
    cfg.mmio_out_path[0] = '\0';
    cfg.run_id[0] = '\0';
    cfg.cpu_list[0] = '\0';

    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i], "--iface") && i+1<argc) cfg.ifname = argv[++i];
        else if(!strcmp(argv[i], "--ifaces") && i+1<argc) cfg.ifaces = argv[++i];
        else if(!strcmp(argv[i], "--ring-mem") && i+1<argc) cfg.ring_mem = strtoull(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--frame-size") && i+1<argc) cfg.frame_size = (uint32_t)strtoul(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--block-size") && i+1<argc) cfg.block_size = (uint32_t)strtoul(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--timeout-ms") && i+1<argc) cfg.timeout_ms = (uint32_t)strtoul(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--snaplen") && i+1<argc) cfg.snaplen = (uint32_t)strtoul(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--blob-size") && i+1<argc) cfg.blob_size = strtoull(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--huge-dir") && i+1<argc) cfg.huge_dir = argv[++i];
        else if(!strcmp(argv[i], "--blob-name") && i+1<argc) cfg.blob_name = argv[++i];
        else if(!strcmp(argv[i], "--align") && i+1<argc) cfg.align = (uint32_t)strtoul(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--duration") && i+1<argc) cfg.duration_s = strtod(argv[++i], NULL);
        else if(!strcmp(argv[i], "--quiet")) cfg.verbose = 0;
        else if(!strcmp(argv[i], "--pcpu") && i+1<argc) cfg.pcpu_enable = (int)strtol(argv[++i], NULL, 10);
        else if(!strcmp(argv[i], "--prog") && i+1<argc) cfg.prog = argv[++i];
        else if(!strcmp(argv[i], "--pcpu-metrics") && i+1<argc) cfg.pcpu_metrics = (int)strtol(argv[++i], NULL, 10);
        else if(!strcmp(argv[i], "--fanout-id") && i+1<argc) cfg.fanout_id = (int)strtol(argv[++i], NULL, 0);
        else if(!strcmp(argv[i], "--fanout-mode") && i+1<argc) {
            const char* m = argv[++i];
            if(!strcmp(m,"hash")) cfg.fanout_mode = 1; else if(!strcmp(m,"lb")) cfg.fanout_mode = 2; else cfg.fanout_mode = 0;
        }
        else if(!strcmp(argv[i], "--llvm-opt") && i+1<argc) cfg.llvm_opt = (int)strtol(argv[++i], NULL, 10);
        else if(!strcmp(argv[i], "--llvm-hint") && i+1<argc) cfg.llvm_hint = argv[++i];
        else if(!strcmp(argv[i], "--peek-mmio") && i+1<argc) cfg.peek_mmio = (int)strtol(argv[++i], NULL, 10);
        else if(!strcmp(argv[i], "--peek-bdf") && i+1<argc) cfg.peek_bdf = argv[++i];
        else if(!strcmp(argv[i], "--plan-out") && i+1<argc) cfg.plan_out = argv[++i];
        else if(!strcmp(argv[i], "--pin-cpu-list") && i+1<argc){
            strncpy(cfg.cpu_list, argv[++i], sizeof(cfg.cpu_list)-1);
            cfg.cpu_list[sizeof(cfg.cpu_list)-1] = '\0';
        }
        else if(!strcmp(argv[i], "-h") || !strcmp(argv[i], "--help")){
            fprintf(stderr,
                "Usage: %s --iface IF|--ifaces IF1,IF2 --blob-size BYTES [--ring-mem B] [--frame-size N] [--block-size N]\\n"
                "          [--snaplen N] [--align N] [--duration S] [--pcpu 0|1] [--pcpu-metrics 0|1] [--prog STR] [--fanout-id N] [--fanout-mode hash|lb]\\n"
                "          [--llvm-opt 0|1] [--llvm-hint STR] [--plan-out PATH] [--pin-cpu-list STR] [--quiet]\n",
                argv[0]);
            return 0;
        }
    }

    // Create run_id and capture CPU pinning list (honor override if provided)
    snprintf(cfg.run_id, sizeof(cfg.run_id), "%ld-%d", (long)time(NULL), getpid());
    if(!cfg.cpu_list[0]){ read_cpu_list(cfg.cpu_list, sizeof(cfg.cpu_list)); }

    if(cfg.verbose){
        fprintf(stderr, "[AFPKT] if=%s ifaces=%s ring_mem=%zu frame=%u block=%u snap=%u blob=%zu align=%u dur=%.2fs pcpu=%d fanout=(id=%d,mode=%d) autotune=%d llvm_opt=%d hint=%s pin=%s\n",
                cfg.ifname, (cfg.ifaces?cfg.ifaces:"-"), cfg.ring_mem, cfg.frame_size, cfg.block_size, cfg.snaplen, cfg.blob_size, cfg.align, cfg.duration_s, cfg.pcpu_enable, cfg.fanout_id, cfg.fanout_mode, cfg.auto_tune, cfg.llvm_opt, (cfg.llvm_hint?cfg.llvm_hint:"-"), cfg.cpu_list[0]?cfg.cpu_list:"-");
    }

    // LLVM-inspired optimizer: choose defaults and print a plan (no JIT yet)
    if(cfg.llvm_opt){
        const char* plan_op = "counteq:0"; // default
        uint32_t plan_align = cfg.align ? cfg.align : 64;
        uint32_t plan_snap = cfg.snaplen ? cfg.snaplen : 2048;
        if(cfg.llvm_hint){
            if(strstr(cfg.llvm_hint, "matrix")||strstr(cfg.llvm_hint, "hist")) {
                plan_op = "hist8"; plan_align = (plan_align < 64) ? 64 : plan_align; plan_snap = (plan_snap < 1024)?1024:plan_snap;
            } else if(strstr(cfg.llvm_hint, "crc")||strstr(cfg.llvm_hint, "network")) {
                plan_op = "crc32c"; plan_align = (plan_align < 64)?64:plan_align; plan_snap = (plan_snap < 512)?512:plan_snap;
            } else if(strstr(cfg.llvm_hint, "xor")) {
                plan_op = "xor:0"; plan_align = (plan_align < 64)?64:plan_align;
            } else if(strstr(cfg.llvm_hint, "add")) {
                plan_op = "add:0"; plan_align = (plan_align < 64)?64:plan_align;
            }
        }
        fprintf(stderr, "[OPT] plan: op=%s align=%u snap=%u (hint=%s)\n", plan_op, plan_align, plan_snap, (cfg.llvm_hint?cfg.llvm_hint:"-"));
        // Apply plan as soft defaults if user didn’t specify overrides
        if(!cfg.pcpu_enable) cfg.pcpu_enable = 1;
        if(!cfg.prog) cfg.prog = plan_op;
        if(cfg.align == 0) cfg.align = plan_align;
        if(cfg.snaplen == 0) cfg.snaplen = plan_snap;
    }

    // Map huge blob
    PfsHugeBlob blob; memset(&blob, 0, sizeof(blob));
    if(pfs_hugeblob_map(cfg.blob_size, cfg.huge_dir, cfg.blob_name, &blob) != 0){
        perror("pfs_hugeblob_map");
        return 1;
    }
    pfs_hugeblob_set_keep(&blob, 1);

    // Determine interfaces list
    char ifnames[MAX_IFACES][IFNAMSIZ]; int ifn = 0;
    if(cfg.ifaces && *cfg.ifaces){
        char* tmp = strdup(cfg.ifaces); if(!tmp){ fprintf(stderr, "oom\n"); return 1; }
        char* save=NULL; char* tok=strtok_r(tmp, ",", &save);
        while(tok && ifn < MAX_IFACES){
            while(*tok==' '||*tok=='\t') tok++;
            strncpy(ifnames[ifn], tok, IFNAMSIZ-1); ifnames[ifn][IFNAMSIZ-1]='\0';
            ifn++; tok = strtok_r(NULL, ",", &save);
        }
        free(tmp);
    } else {
        strncpy(ifnames[0], cfg.ifname, IFNAMSIZ-1); ifnames[0][IFNAMSIZ-1]='\0'; ifn = 1;
    }

    // Create rings
    KRing* rings = (KRing*)calloc(ifn, sizeof(KRing)); if(!rings){ fprintf(stderr, "oom rings\n"); pfs_hugeblob_unmap(&blob); return 1; }
    uint32_t* cur_blocks = (uint32_t*)calloc(ifn, sizeof(uint32_t)); if(!cur_blocks){ fprintf(stderr, "oom cur_blocks\n"); free(rings); pfs_hugeblob_unmap(&blob); return 1; }
    struct pollfd* pfds = (struct pollfd*)calloc(ifn, sizeof(struct pollfd)); if(!pfds){ fprintf(stderr, "oom pfds\n"); free(cur_blocks); free(rings); pfs_hugeblob_unmap(&blob); return 1; }

    for(int i=0;i<ifn;i++){
        Cfg xcfg = cfg; xcfg.ifname = ifnames[i];
        if(setup_kernel_ring(&xcfg, &rings[i]) != 0){
            fprintf(stderr, "setup_kernel_ring failed for %s\n", ifnames[i]);
            for(int j=0;j<i;j++){ teardown_kernel_ring(&rings[j]); }
            free(pfds); free(cur_blocks); free(rings); pfs_hugeblob_unmap(&blob); return 1;
        }
        cur_blocks[i] = 0;
        pfds[i].fd = rings[i].fd; pfds[i].events = POLLIN;
    }

    // Optionally perform MMIO peek via pfs_ringpeek and record path
    if(cfg.peek_mmio){
        char ts[32]; iso8601_utc(ts, sizeof(ts));
        snprintf(cfg.mmio_out_path, sizeof(cfg.mmio_out_path), "logs/mmio_%s.txt", ts);
        if(mmio_peek_to_file(&cfg, cfg.mmio_out_path) != 0){ cfg.mmio_out_path[0] = '\0'; }
    }

    // Pre-allocate metadata ring sized to the largest frame_nr among sockets
    uint32_t frame_nr_max = 0;
    for(int i=0;i<ifn;i++) if(rings[i].req.tp_frame_nr > frame_nr_max) frame_nr_max = rings[i].req.tp_frame_nr;
    PacketMeta* meta = (PacketMeta*)aligned_alloc(64, (size_t)frame_nr_max * sizeof(PacketMeta));
    if(!meta){ fprintf(stderr, "alloc meta failed\n"); for(int i=0;i<ifn;i++) teardown_kernel_ring(&rings[i]); free(pfds); free(cur_blocks); free(rings); pfs_hugeblob_unmap(&blob); return 1; }
    memset(meta, 0, (size_t)frame_nr_max * sizeof(PacketMeta));

    // Write plan JSON (before capture)
    // Extend outputs.debug.mmio if available
    write_plan_json(&cfg, ifnames, ifn, rings, blob.size);

    // Main loop: walk blocks per socket -> frames, copy into user blob
    uint64_t pkt_cnt = 0, byte_cnt = 0, drops = 0;
    uint64_t wr = 0; // write offset into blob
    uint64_t pcpu_bytes = 0; // per-interval counter when pcpu_metrics

    // Metrics JSONL writer
    struct stat lst; if(stat("logs", &lst)!=0) mkdir("logs", 0755);
    char metrics_path[256]; snprintf(metrics_path, sizeof(metrics_path), "logs/pfs_afpkt_rx_stats_%s.jsonl", cfg.run_id);
    FILE* mfp = fopen(metrics_path, "a");
    char pin_list[256]; strncpy(pin_list, cfg.cpu_list, sizeof(pin_list)-1); pin_list[sizeof(pin_list)-1]='\0';

    double t0 = now_sec(), tlast = t0;

    while(!g_stop){
        if(cfg.duration_s > 0 && (now_sec() - t0) >= cfg.duration_s) break;
        int pr = poll(pfds, ifn, (int)cfg.timeout_ms);
        if(pr < 0){ if(errno == EINTR) continue; perror("poll"); break; }

        for(int si=0; si<ifn; si++){
            // Process at most one block per socket per loop
            KRing* kr = &rings[si];
            uint32_t* pcb = &cur_blocks[si];
            char* base = (char*)kr->map + (size_t)(*pcb) * kr->req.tp_block_size;
            struct tpacket_block_desc* bd = (struct tpacket_block_desc*)base;
            if(!(bd->hdr.bh1.block_status & TP_STATUS_USER)){
                *pcb = (*pcb + 1) % kr->req.tp_block_nr;
                continue;
            }
            uint32_t num_pkts = bd->hdr.bh1.num_pkts;
            uint32_t offset = bd->hdr.bh1.offset_to_first_pkt;
            for(uint32_t i=0; i<num_pkts; i++){
                struct tpacket3_hdr* thdr = (struct tpacket3_hdr*)(base + offset);
                uint8_t* pkt = (uint8_t*)thdr + thdr->tp_mac;
                uint32_t caplen = (thdr->tp_snaplen < cfg.snaplen) ? thdr->tp_snaplen : cfg.snaplen;
                // Copy to huge blob (aligned)
                if(cfg.align){ wr = (wr + (cfg.align - 1)) & ~((uint64_t)cfg.align - 1ULL); }
                if(wr + caplen > blob.size){ wr = 0; if(cfg.align) wr &= ~((uint64_t)cfg.align - 1ULL); }
                if(caplen <= blob.size){
                    // prefetch destination and source
                    __builtin_prefetch((uint8_t*)blob.addr + wr, 1, 3);
                    __builtin_prefetch(pkt, 0, 3);
                    memcpy((uint8_t*)blob.addr + wr, pkt, caplen);
                    size_t midx = (size_t)(pkt_cnt % frame_nr_max);
                    meta[midx].off = wr;
                    meta[midx].len = caplen;
                    meta[midx].rxhash = thdr->hv1.tp_rxhash;
                    if(cfg.pcpu_enable && caplen > 0){
                        PfsGramDesc d; d.offset = wr; d.len = caplen; d.flags = 0;
                        pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
                        pfs_pcpu_op_t op = PFS_PCPU_OP_COUNT_EQ_IMM8; uint8_t imm = 0;
                        if(cfg.prog && *cfg.prog){
                            if(!strncmp(cfg.prog, "counteq:", 8)) { op = PFS_PCPU_OP_COUNT_EQ_IMM8; imm = (uint8_t)strtoul(cfg.prog+8,NULL,0); }
                            else if(!strcmp(cfg.prog, "fnv")||!strcmp(cfg.prog,"fnv64")) { op = PFS_PCPU_OP_CHECKSUM_FNV64; imm = 0; }
                            else if(!strcmp(cfg.prog, "crc32c")) { op = PFS_PCPU_OP_CHECKSUM_CRC32C; imm = 0; }
                            else if(!strncmp(cfg.prog, "xor:",4)) { op = PFS_PCPU_OP_XOR_IMM8; imm=(uint8_t)strtoul(cfg.prog+4,NULL,0); }
                            else if(!strncmp(cfg.prog, "add:",4)) { op = PFS_PCPU_OP_ADD_IMM8; imm=(uint8_t)strtoul(cfg.prog+4,NULL,0); }
                            else if(!strncmp(cfg.prog, "hist8",5)) { op = PFS_PCPU_OP_HIST8; imm=0; }
                        }
                        (void)pfs_pcpu_apply(blob.addr, blob.size, &d, 1, op, imm, 1469598103934665603ULL, &mm);
                        if(cfg.pcpu_metrics) pcpu_bytes += mm.bytes_touched;
                    }
                    wr += caplen;
                    pkt_cnt++;
                    byte_cnt += caplen;
                }
                offset += thdr->tp_next_offset;
            }
            bd->hdr.bh1.block_status = TP_STATUS_KERNEL;
            __sync_synchronize();
            *pcb = (*pcb + 1) % kr->req.tp_block_nr;
        }

        double tn = now_sec();
        if(cfg.verbose && (tn - tlast) >= 0.5){
            double mb = byte_cnt / 1e6; double mbps = mb / (tn - t0 + 1e-9);
            if(cfg.pcpu_metrics){
                double pmb = (double)pcpu_bytes / 1e6; double pmbps = pmb / (tn - t0 + 1e-9);
                fprintf(stderr, "[AFPKT] pkts=%llu bytes=%.1f MB avg=%.1f MB/s pcpu_bytes=%.1f MB pcpu_avg=%.1f MB/s wr_off=%llu\n",
                        (unsigned long long)pkt_cnt, mb, mbps, pmb, pmbps, (unsigned long long)wr);
            } else {
                fprintf(stderr, "[AFPKT] pkts=%llu bytes=%.1f MB avg=%.1f MB/s wr_off=%llu\n",
                        (unsigned long long)pkt_cnt, mb, mbps, (unsigned long long)wr);
            }
            if(cfg.llvm_opt){
                fprintf(stderr, "[OPT] active: op=%s align=%u snap=%u fanout=(id=%d,mode=%d)\n",
                        (cfg.prog?cfg.prog:""), cfg.align, cfg.snaplen, cfg.fanout_id, cfg.fanout_mode);
            }
            // Emit metrics JSONL
            if(mfp){
                char ts2[32]; iso8601_utc(ts2, sizeof(ts2));
                if(cfg.pcpu_metrics){
                    double pmb = (double)pcpu_bytes / 1e6; double pmbps = pmb / (tn - t0 + 1e-9);
                    fprintf(mfp, "{\"run_id\":\"%s\",\"ts\":\"%s\",\"iface\":\"%s\",\"cpu_list\":\"%s\",\"pkts\":%llu,\"bytes\":%llu,\"avg_mbps\":%.3f,\"pcpu_bytes\":%llu,\"pcpu_avg_mbps\":%.3f,\"wr_off\":%llu}\n",
                        cfg.run_id, ts2, ifnames[0], pin_list,
                        (unsigned long long)pkt_cnt, (unsigned long long)byte_cnt, mbps,
                        (unsigned long long)pcpu_bytes, pmbps,
                        (unsigned long long)wr);
                } else {
                    fprintf(mfp, "{\"run_id\":\"%s\",\"ts\":\"%s\",\"iface\":\"%s\",\"cpu_list\":\"%s\",\"pkts\":%llu,\"bytes\":%llu,\"avg_mbps\":%.3f,\"wr_off\":%llu}\n",
                        cfg.run_id, ts2, ifnames[0], pin_list,
                        (unsigned long long)pkt_cnt, (unsigned long long)byte_cnt, mbps,
                        (unsigned long long)wr);
                }
                fflush(mfp);
            }
            tlast = tn;
        }
    }

    double t1 = now_sec();
    double mb = byte_cnt / 1e6; double mbps = mb / (t1 - t0 + 1e-9);
    if(cfg.pcpu_metrics){
        double pmb = (double)pcpu_bytes / 1e6; double pmbps = pmb / (t1 - t0 + 1e-9);
        fprintf(stderr, "[AFPKT DONE] pkts=%llu bytes=%.1f MB elapsed=%.3f s avg=%.1f MB/s pcpu_bytes=%.1f MB pcpu_avg=%.1f MB/s blob=%s/%s size=%zu\n",
                (unsigned long long)pkt_cnt, mb, (t1 - t0), mbps, pmb, pmbps, cfg.huge_dir, cfg.blob_name, blob.size);
    } else {
        fprintf(stderr, "[AFPKT DONE] pkts=%llu bytes=%.1f MB elapsed=%.3f s avg=%.1f MB/s blob=%s/%s size=%zu\n",
                (unsigned long long)pkt_cnt, mb, (t1 - t0), mbps, cfg.huge_dir, cfg.blob_name, blob.size);
    }

    free(meta);
    for(int i=0;i<ifn;i++) teardown_kernel_ring(&rings[i]);
    free(pfds); free(cur_blocks); free(rings);
    if(mfp) fclose(mfp);
    pfs_hugeblob_unmap(&blob);
    return 0;
}
