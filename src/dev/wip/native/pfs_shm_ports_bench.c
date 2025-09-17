#define _GNU_SOURCE
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <stdatomic.h>

// PacketFS internals
#include "../../realsrc/packetfs/memory/pfs_hugeblob.h"
#include "../../realsrc/packetfs/pcpu/pfs_pcpu.h"
#include "../../realsrc/packetfs/gram/pfs_gram.h"
#include <dlfcn.h>

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop = 1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static inline uint64_t xorshift64(uint64_t x){ x ^= x >> 12; x ^= x << 25; x ^= x >> 27; return x * 2685821657736338717ULL; }

static void usage(const char* prog){
  fprintf(stderr,
    "Usage: %s --blob-size BYTES [--huge-dir DIR] [--blob-name NAME]\n"
    "          [--ports P] [--queues Q] [--dpf N] [--align A] [--seg-len L]\n"
    "          [--duration S] [--pcpu 0|1] [--pcpu-op fnv|crc32c|xor|add|counteq|hist8] [--imm N]\n",
    prog);
}

int main(int argc, char** argv){
  signal(SIGINT, on_sigint);

  // Config (single-core, single-thread producer->consumer in a loop)
  size_t blob_size = 2ULL<<30; // 2 GiB
  const char* huge_dir = "/dev/hugepages";
  const char* blob_name = "pfs_shm_ports_blob";
  int ports = 4;
  int queues = 2;
  uint32_t dpf = 64;
  uint32_t align = 64;
  uint32_t seg_len = 80; // contiguous segment length
  double duration_s = 10.0;
  int pcpu_enable = 1;
  pfs_pcpu_op_t pcpu_op = PFS_PCPU_OP_COUNT_EQ_IMM8;
  uint8_t pcpu_imm = 0;
  int verbose = 1;
  const char* jit_so = NULL; // optional path to shared object implementing pfs_jit_span

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--blob-size") && i+1<argc) blob_size = strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) huge_dir = argv[++i];
    else if(!strcmp(argv[i],"--blob-name") && i+1<argc) blob_name = argv[++i];
    else if(!strcmp(argv[i],"--ports") && i+1<argc) ports = (int)strtol(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--queues") && i+1<argc) queues = (int)strtol(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--dpf") && i+1<argc) dpf = (uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--align") && i+1<argc) align = (uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--seg-len") && i+1<argc) seg_len = (uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--duration") && i+1<argc) duration_s = strtod(argv[++i],NULL);
    else if(!strcmp(argv[i],"--pcpu") && i+1<argc) pcpu_enable = (int)strtol(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--pcpu-op") && i+1<argc){
      const char* o = argv[++i];
      if(!strcmp(o,"fnv")||!strcmp(o,"fnv64")) pcpu_op = PFS_PCPU_OP_CHECKSUM_FNV64;
      else if(!strcmp(o,"crc32c")) pcpu_op = PFS_PCPU_OP_CHECKSUM_CRC32C;
      else if(!strcmp(o,"xor")) pcpu_op = PFS_PCPU_OP_XOR_IMM8;
      else if(!strcmp(o,"add")) pcpu_op = PFS_PCPU_OP_ADD_IMM8;
      else if(!strcmp(o,"counteq")) pcpu_op = PFS_PCPU_OP_COUNT_EQ_IMM8;
      else if(!strcmp(o,"hist8")) pcpu_op = PFS_PCPU_OP_HIST8;
    }
    else if(!strcmp(argv[i],"--imm") && i+1<argc) pcpu_imm = (uint8_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--jit-so") && i+1<argc) jit_so = argv[++i];
    else if(!strcmp(argv[i],"--quiet")) verbose = 0;
    else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")){ usage(argv[0]); return 0; }
  }

  if(verbose){
    fprintf(stderr,"[SHM-PORTS] blob=%zu dir=%s name=%s P=%d Q=%d dpf=%u align=%u seg=%u dur=%.2f pcpu=%d op=%d imm=%u\n",
      (size_t)blob_size, huge_dir, blob_name, ports, queues, dpf, align, seg_len, duration_s, pcpu_enable, (int)pcpu_op, (unsigned)pcpu_imm);
  }

  // Map blob
  PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, huge_dir, blob_name, &blob)!=0){ fprintf(stderr,"map blob: %s\n", strerror(errno)); return 1; }
  pfs_hugeblob_set_keep(&blob, 1);

  // Per-ring contiguous offset state
  uint32_t rings_n = (uint32_t)((ports>0?ports:1) * (queues>0?queues:1));
  uint64_t* contig_off = (uint64_t*)calloc(rings_n, sizeof(uint64_t));
  if(!contig_off){ fprintf(stderr,"alloc contig_off failed\n"); return 1; }

  // JIT loader (optional)
  typedef void (*pfs_jit_span_fn)(uint8_t* ptr, uint32_t len, uint8_t imm, uint64_t* acc);
  void* jit_handle = NULL; pfs_jit_span_fn jit_fn = NULL; uint64_t jit_acc = 0;
  if(jit_so && *jit_so){
    jit_handle = dlopen(jit_so, RTLD_NOW);
    if(!jit_handle){ fprintf(stderr, "[SHM-PORTS] dlopen failed: %s\n", dlerror()); }
    else {
      jit_fn = (pfs_jit_span_fn)dlsym(jit_handle, "pfs_jit_span");
      if(!jit_fn){ fprintf(stderr, "[SHM-PORTS] dlsym pfs_jit_span failed: %s\n", dlerror()); }
    }
  }

  // Single-thread loop across rings
  const uint64_t base = blob.size / 2;
  uint64_t frames = 0, bytes_eff = 0;
  pfs_pcpu_metrics_t pcpu_m; memset(&pcpu_m, 0, sizeof(pcpu_m));

  uint64_t x = 0x12345678ULL;
  double t0 = now_sec(), tlast = t0;

  while(!g_stop){
    double tn = now_sec();
    if(duration_s>0 && (tn - t0) >= duration_s) break;

    uint32_t r = (uint32_t)(frames % rings_n);
    // Build dpf descriptors contiguous for ring r
    PfsGramDesc descs[1024]; if(dpf > 1024) dpf = 1024;
    uint64_t off = contig_off[r];
    if(off == 0){ off = (blob.size/4) & ~((uint64_t)align - 1ULL); }
    uint64_t eff = 0;
    for(uint32_t i=0;i<dpf;i++){
      uint64_t seg = seg_len ? seg_len : 80;
      if(align) seg = (seg + align - 1) & ~((uint64_t)align - 1ULL);
      if(off + seg > blob.size){ off = (blob.size/4) & ~((uint64_t)align - 1ULL); }
      descs[i].offset = off; descs[i].len = (uint32_t)seg; descs[i].flags = 0u; // absolute offsets
      eff += seg; off += seg;
    }
    contig_off[r] = off;

    // Apply pCPU (arithmetic reduction)
    if(pcpu_enable){
      if(jit_fn){
        for(uint32_t i=0;i<dpf;i++){
          uint64_t off = descs[i].offset; uint32_t len = descs[i].len;
          if(off >= blob.size) continue;
          if(off + (uint64_t)len > blob.size) len = (uint32_t)(blob.size - off);
          if(len==0) continue;
          uint8_t* ptr = (uint8_t*)blob.addr + off;
          jit_fn(ptr, len, pcpu_imm, &jit_acc);
          pcpu_m.bytes_total += len;
          pcpu_m.bytes_touched += len;
          pcpu_m.desc_count += 1;
        }
      } else {
        pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
        (void)pfs_pcpu_apply(blob.addr, blob.size, (const PfsGramDesc*)descs, dpf, pcpu_op, pcpu_imm, 1469598103934665603ULL, &mm);
        pcpu_m.bytes_total += mm.bytes_total;
        pcpu_m.bytes_touched += mm.bytes_touched;
        pcpu_m.desc_count += mm.desc_count;
        pcpu_m.ns += mm.ns;
        pcpu_m.checksum_out ^= mm.checksum_out;
      }
    }

    bytes_eff += eff;
    frames++;

    if(verbose && (tn - tlast) >= 0.5){
      double mb = (double)bytes_eff / 1e6;
      double mbps = mb / (tn - t0);
      fprintf(stderr, "[SHM-PORTS] eff=%.1f MB avg=%.1f MB/s frames=%llu\n", mb, mbps, (unsigned long long)frames);
      tlast = tn;
    }
  }

  double t1 = now_sec();
  double eff_mb = (double)bytes_eff / 1e6;
  double eff_mbps = (t1 > t0) ? (eff_mb / (t1 - t0)) : 0.0;
  fprintf(stderr, "[SHM-PORTS DONE] eff_bytes=%llu (%.1f MB) elapsed=%.3f s avg=%.1f MB/s frames=%llu\n",
          (unsigned long long)bytes_eff, eff_mb, (t1 - t0), eff_mbps, (unsigned long long)frames);

// pwnCPU metrics (effective vs CPU baseline)
  if(pcpu_enable){
    // Measure CPU baseline MBps in-process over a limited slice of the blob
    // Map pCPU op to a baseline micro-op we can time cheaply
    enum { SAMPLE_MB = 256 }; // 256MB sample for baseline
    size_t sample_bytes = (size_t)SAMPLE_MB * 1024 * 1024;
    if(sample_bytes > blob.size) sample_bytes = blob.size;
    uint8_t* p = (uint8_t*)blob.addr;
    // Choose a pointer safely within blob
    size_t start = (blob.size/8) & ~((size_t)align - 1ULL);
    if(start + sample_bytes > blob.size) start = 0;
    p += start;

    // Select a baseline op (checksum/xor/add)
    int baseline_mode = 0; // 0=checksum, 1=xor8, 2=add8
    if(pcpu_op == PFS_PCPU_OP_XOR_IMM8) baseline_mode = 1;
    else if(pcpu_op == PFS_PCPU_OP_ADD_IMM8) baseline_mode = 2;
    else baseline_mode = 0; // default checksum for others

    uint64_t t0n, t1n; t0n = 0; t1n = 0;
    // Warmup touch to fault in pages
    volatile uint8_t sink = 0; for(size_t i=0;i<4096 && i<sample_bytes;i+=64) sink ^= p[i]; (void)sink;
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); t0n = (uint64_t)ts.tv_sec*1000000000ull + (uint64_t)ts.tv_nsec;
    if(baseline_mode == 0){ // checksum (FNV-1a)
      uint64_t h = 1469598103934665603ULL;
      size_t processed = 0;
      while(processed < sample_bytes){
        size_t chunk = (sample_bytes - processed) > 1<<22 ? 1<<22 : (sample_bytes - processed); // 4MB chunks
        // inline FNV
        const uint8_t* q = p + processed;
        for(size_t k=0;k<chunk;k++){ h ^= q[k]; h *= 1099511628211ULL; }
        processed += chunk;
      }
      (void)h;
    } else if(baseline_mode == 1){ // xor8
      uint8_t v = pcpu_imm;
      for(size_t i=0;i<sample_bytes;i++){ p[i] ^= v; }
    } else { // add8
      uint8_t v = pcpu_imm;
      for(size_t i=0;i<sample_bytes;i++){ p[i] = (uint8_t)(p[i] + v); }
    }
    clock_gettime(CLOCK_MONOTONIC, &ts); t1n = (uint64_t)ts.tv_sec*1000000000ull + (uint64_t)ts.tv_nsec;
    double sec = (double)(t1n - t0n)/1e9;
    double cpu_mbps = sec>0.0 ? ((double)sample_bytes/1e6)/sec : 0.0;

    double pc_mb = (double)pcpu_m.bytes_touched / 1e6;
    double pc_mbps = (t1>t0) ? (pc_mb / (t1 - t0)) : 0.0;
    double pwn_exec_tp = (cpu_mbps>0.0) ? (pc_mbps / cpu_mbps) : 0.0;
    double pwn_eff_tp  = (cpu_mbps>0.0) ? (eff_mbps / cpu_mbps) : 0.0;
    double pwn_exec_t  = (cpu_mbps>0.0 && pc_mb>0.0) ? ((t1 - t0) / (pc_mb / cpu_mbps)) : 0.0;
    double pwn_eff_t   = (cpu_mbps>0.0 && eff_mb>0.0) ? ((t1 - t0) / (eff_mb / cpu_mbps)) : 0.0;
    fprintf(stderr, "[SHM-PORTS PCPU] touched=%.3f MB pcpu_MBps=%.1f eff_MBps=%.1f baseline_MBps=%.3f pwnCPU_exec_tp=%.6f pwnCPU_eff_tp=%.6f pwnCPU_exec_t=%.6f pwnCPU_eff_t=%.6f\n",
            pc_mb, pc_mbps, eff_mbps, cpu_mbps, pwn_exec_tp, pwn_eff_tp, pwn_exec_t, pwn_eff_t);
  }

  free(contig_off);
  if(jit_handle) dlclose(jit_handle);
  pfs_hugeblob_unmap(&blob);
  return 0;
}

