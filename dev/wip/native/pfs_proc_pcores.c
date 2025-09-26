// SPDX-License-Identifier: MIT
// Multi-process pcores benchmark over hugepages SPSC rings (no VMs)
// Parent = producer; N children = consumers (one per ring)
// Records: [u32 dpf][PfsGramDesc[dpf]] stored in each ring's slab
// Metrics: shared stats array in a channel header for CPUpwn computation

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <time.h>
#include <signal.h>
#include <sched.h>
#include <sys/stat.h>
#include <pthread.h>

#include "../../src/packetfs/uapi/pfs_fastpath.h"  // reuse pfs_fp_ring_hdr
#include "../../src/packetfs/memory/pfs_hugeblob.h"
#include "../../src/packetfs/pcpu/pfs_pcpu.h"
#include "../../src/packetfs/gram/pfs_gram.h"

static uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }
static inline uint32_t rr32(uint32_t *x){ *x ^= *x>>13; *x ^= *x<<17; *x ^= *x>>5; return *x; }

// Shared channel header at the start of the mapping
typedef struct {
  uint32_t ring_count;       // N pcores
  uint32_t ring_pow2;        // slots per ring = 2^ring_pow2
  uint32_t dpf;              // descriptors per frame
  uint32_t align;            // alignment for offsets/len
  uint64_t duration_ns;      // test duration
  uint64_t stats_off;        // offset to stats array
  uint64_t rings_base_off;   // offset to first ring section
  uint64_t ring_section_bytes; // bytes per ring section
  uint64_t slab_bytes;       // bytes of per-ring slab
  uint64_t reserved[8];
} ChanHdr;

typedef struct {
  volatile uint64_t bytes_eff;
  volatile uint64_t frames;
} PcoreStats;

static void pin_cpu(int cpu){
  cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set); sched_setaffinity(0, sizeof(set), &set);
}

static int consumer_proc(uint8_t *chan_base, ChanHdr *ch, int idx, void *blob_base, size_t blob_size,
                         const pfs_pcpu_op_t *ops, const uint8_t *imms, size_t prog_n){
  // locate structures for ring idx
  uint8_t *rs = chan_base + ch->rings_base_off + (size_t)idx * ch->ring_section_bytes;
  struct pfs_fp_ring_hdr *hdr = (struct pfs_fp_ring_hdr*)rs;
  size_t hdr_pad = (sizeof(*hdr)+63)&~63u;
  uint32_t *slots = (uint32_t*)(rs + hdr_pad);
  uint8_t *slab = rs + hdr->data_offset;
  PcoreStats *stats = (PcoreStats*)(chan_base + ch->stats_off);
  PcoreStats *st = &stats[idx];
  uint64_t t0=now_ns();
  while(now_ns()-t0 < ch->duration_ns){
    uint32_t head = __atomic_load_n(&hdr->head, __ATOMIC_RELAXED);
    uint32_t tail = __atomic_load_n(&hdr->tail, __ATOMIC_ACQUIRE);
    if(head == tail){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue; }
    uint32_t rec_off = slots[head];
    uint8_t *rec = slab + rec_off;
    uint32_t dpf = *(uint32_t*)rec;
    PfsGramDesc *descs = (PfsGramDesc*)(rec + sizeof(uint32_t));
    uint64_t touched_total = 0;
    if (prog_n == 0){
      pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
      (void)pfs_pcpu_apply(blob_base, blob_size, descs, dpf, PFS_PCPU_OP_XOR_IMM8, 255, 1469598103934665603ULL, &mm);
      touched_total = mm.bytes_touched;
    } else {
      for(size_t k=0;k<prog_n;k++){
        pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
        (void)pfs_pcpu_apply(blob_base, blob_size, descs, dpf, ops[k], imms[k], 1469598103934665603ULL, &mm);
        touched_total += mm.bytes_touched;
      }
    }
    __atomic_store_n(&hdr->head, (head+1)&hdr->mask, __ATOMIC_RELEASE);
    __atomic_fetch_add(&st->bytes_eff, touched_total, __ATOMIC_RELAXED);
    __atomic_fetch_add(&st->frames, 1ull, __ATOMIC_RELAXED);
  }
  return 0;
}

static double run_cpu_baseline(void *blob_base, size_t blob_size, uint32_t dpf, uint32_t align, pfs_pcpu_op_t op, uint8_t imm, double seconds,
                               uint64_t range_base, uint64_t range_len){
  uint64_t t0=now_ns(); uint64_t tend=t0 + (uint64_t)(seconds*1e9);
  uint64_t bytes=0; uint32_t x=0x1a2b3c4d;
  PfsGramDesc descs[1024]; if(dpf>1024) dpf=1024;
  uint64_t rb = range_base; uint64_t rl = (range_len? range_len : blob_size);
  if (rb + rl > blob_size) rl = (rb<blob_size)? (blob_size - rb) : 0;
  if (rl == 0) return 0.0;
  while(now_ns()<tend){
    for(uint32_t i=0;i<dpf;i++){
      rr32(&x);
      uint32_t len = (x % (align? align*4 : 4096)) + align; if(len>262144u) len=262144u;
      if (len > rl) len = (uint32_t)rl;
      uint64_t off = rb + (x % (rl? rl : 1)); if(align) off &= ~((uint64_t)align-1ULL);
      if (off < rb) off = rb;
      if(off+len>rb+rl){ off = rb + rl - len; if(align) off &= ~((uint64_t)align-1ULL); if(off+len>rb+rl){ if(len>align) len=(uint32_t)align; off=rb; } }
      descs[i].offset=off; descs[i].len=len; descs[i].flags=0;
    }
    pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
    (void)pfs_pcpu_apply(blob_base, blob_size, descs, dpf, op, imm, 1469598103934665603ULL, &mm);
    bytes += mm.bytes_touched;
  }
  double secs = (now_ns()-t0)/1e9; if(secs<=0) secs=1e-6;
  return (bytes/1e6)/secs; // MB/s
}

// New: multi-thread CPU baseline using pfs_pcpu_apply with N threads (apples-to-apples vs pcores)
typedef struct {
  void *blob_base; size_t blob_size; uint32_t dpf; uint32_t align; pfs_pcpu_op_t op; uint8_t imm;
  uint64_t rb; uint64_t rl; uint64_t tend;
  volatile uint64_t *bytes_accum;
} BaselineArgs;

static void *baseline_worker(void *arg){
  BaselineArgs *ba = (BaselineArgs*)arg;
  uint32_t x = (uint32_t)(0x9e3779b9u ^ (uintptr_t)ba ^ (uint32_t)now_ns());
  PfsGramDesc descs[1024]; uint32_t dpf = ba->dpf; if(dpf>1024) dpf=1024;
  while(now_ns() < ba->tend){
    for(uint32_t i=0;i<dpf;i++){
      rr32(&x);
      uint32_t len = (x % (ba->align? ba->align*4 : 4096)) + ba->align; if(len>262144u) len=262144u;
      if (len > ba->rl) len = (uint32_t)ba->rl;
      uint64_t off = ba->rb + (x % (ba->rl? ba->rl : 1)); if(ba->align) off &= ~((uint64_t)ba->align-1ULL);
      if (off < ba->rb) off = ba->rb;
      if(off+len>ba->rb+ba->rl){ off = ba->rb + ba->rl - len; if(ba->align) off &= ~((uint64_t)ba->align-1ULL); if(off+len>ba->rb+ba->rl){ if(len>ba->align) len=(uint32_t)ba->align; off=ba->rb; } }
      descs[i].offset=off; descs[i].len=len; descs[i].flags=0;
    }
    pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
    (void)pfs_pcpu_apply(ba->blob_base, ba->blob_size, descs, dpf, ba->op, ba->imm, 1469598103934665603ULL, &mm);
    __atomic_fetch_add(ba->bytes_accum, mm.bytes_touched, __ATOMIC_RELAXED);
  }
  return NULL;
}

static double run_cpu_baseline_mt(void *blob_base, size_t blob_size, uint32_t dpf, uint32_t align,
                                  pfs_pcpu_op_t op, uint8_t imm, double seconds,
                                  uint64_t range_base, uint64_t range_len, int threads){
  if(threads < 1) threads = 1;
  uint64_t rb = range_base; uint64_t rl = (range_len? range_len : blob_size);
  if (rb + rl > blob_size) rl = (rb<blob_size)? (blob_size - rb) : 0;
  if (rl == 0) return 0.0;
  volatile uint64_t bytes_accum = 0;
  pthread_t *tids = (pthread_t*)calloc((size_t)threads, sizeof(pthread_t));
  BaselineArgs ba = { .blob_base=blob_base, .blob_size=blob_size, .dpf=dpf, .align=align, .op=op, .imm=imm,
                      .rb=rb, .rl=rl, .bytes_accum=&bytes_accum };
  uint64_t t0 = now_ns(); ba.tend = t0 + (uint64_t)(seconds*1e9);
  for(int i=0;i<threads;i++){ pthread_create(&tids[i], NULL, baseline_worker, &ba); }
  for(int i=0;i<threads;i++){ pthread_join(tids[i], NULL); }
  free(tids);
  double secs = (now_ns()-t0)/1e9; if(secs<=0) secs=1e-6;
  return ((double)bytes_accum/1e6)/secs;
}

static size_t parse_prog(const char *s, pfs_pcpu_op_t *ops, uint8_t *imms, size_t max_n){
  if(!s||!*s) return 0;
  char *dup = strdup(s); if(!dup) return 0;
  size_t n=0; char *save=NULL; char *tok=strtok_r(dup, ",", &save);
  while(tok && n<max_n){
    char *name=tok; char *colon=strchr(tok, ':'); unsigned long v=0;
    if(colon){ *colon='\0'; v=strtoul(colon+1,NULL,0); }
    pfs_pcpu_op_t op=PFS_PCPU_OP_XOR_IMM8; uint8_t iv=(uint8_t)v;
    if(!strcmp(name,"fnv")||!strcmp(name,"fnv64")) { op=PFS_PCPU_OP_CHECKSUM_FNV64; iv=0; }
    else if(!strcmp(name,"crc32c")) { op=PFS_PCPU_OP_CHECKSUM_CRC32C; iv=0; }
    else if(!strcmp(name,"xor")) { op=PFS_PCPU_OP_XOR_IMM8; }
    else if(!strcmp(name,"add")) { op=PFS_PCPU_OP_ADD_IMM8; }
    else if(!strcmp(name,"counteq")) { op=PFS_PCPU_OP_COUNT_EQ_IMM8; }
    ops[n]=op; imms[n]=iv; n++;
    tok=strtok_r(NULL, ",", &save);
  }
  free(dup); return n;
}

int main(int argc, char **argv){
  // Defaults
  uint32_t pcores=256; uint32_t ring_pow2=16; uint32_t dpf=64; uint32_t align=64; double duration=10.0;
  size_t blob_size=4ull<<30; const char *huge_dir="/mnt/huge1G"; const char *blob_name="pfs_pcores_blob";
  const char *chan_name="pfs_pcores_chan"; size_t slab_bytes=4ull<<20; // 4 MiB per ring slab
  const char *op_s="xor"; uint8_t imm=255; pfs_pcpu_op_t op=PFS_PCPU_OP_XOR_IMM8;
  double baseline_s=2.0; int do_baseline=1;
int pin_prod=1; int prod_cpu=0; // pin producer by default to CPU 0
int cpu_first=0; int cpu_count=0; // 0 => use all online logical CPUs
  const char *csv_path = "logs/pcores_metrics.csv";
  const char *prog_s=NULL; pfs_pcpu_op_t prog_ops[32]; uint8_t prog_imms[32]; size_t prog_n=0;
  const char *file_path=NULL; uint64_t range_base=0; uint64_t range_len=0;

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--pcores")&&i+1<argc) pcores=(uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--ring-pow2")&&i+1<argc) ring_pow2=(uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--dpf")&&i+1<argc) dpf=(uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--align")&&i+1<argc) align=(uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
    else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_size=(size_t)strtoull(argv[++i],NULL,10)<<20;
    else if(!strcmp(argv[i],"--slab-mb")&&i+1<argc) slab_bytes=(size_t)strtoull(argv[++i],NULL,10)<<20;
    else if(!strcmp(argv[i],"--op")&&i+1<argc) op_s=argv[++i];
    else if(!strcmp(argv[i],"--imm")&&i+1<argc) imm=(uint8_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--no-baseline")) do_baseline=0;
    else if(!strcmp(argv[i],"--no-pin-producer")) pin_prod=0;
    else if(!strcmp(argv[i],"--producer-cpu")&&i+1<argc) prod_cpu=(int)strtol(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--csv")&&i+1<argc) csv_path=argv[++i];
    else if(!strcmp(argv[i],"--prog")&&i+1<argc) prog_s=argv[++i];
    else if(!strcmp(argv[i],"--file")&&i+1<argc) file_path=argv[++i];
    else if(!strcmp(argv[i],"--range-off")&&i+1<argc) range_base=strtoull(argv[++i],NULL,0);
    else if(!strcmp(argv[i],"--range-len")&&i+1<argc) range_len=strtoull(argv[++i],NULL,0);
    else if(!strcmp(argv[i],"--cpu-first")&&i+1<argc) cpu_first=(int)strtol(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--cpu-count")&&i+1<argc) cpu_count=(int)strtol(argv[++i],NULL,10);
  }
  if(!strcmp(op_s,"fnv")||!strcmp(op_s,"fnv64")) op=PFS_PCPU_OP_CHECKSUM_FNV64;
  else if(!strcmp(op_s,"crc32c")) op=PFS_PCPU_OP_CHECKSUM_CRC32C;
  else if(!strcmp(op_s,"xor")) op=PFS_PCPU_OP_XOR_IMM8;
  else if(!strcmp(op_s,"add")) op=PFS_PCPU_OP_ADD_IMM8;
  else if(!strcmp(op_s,"counteq")) op=PFS_PCPU_OP_COUNT_EQ_IMM8;
  if(prog_s){ prog_n = parse_prog(prog_s, prog_ops, prog_imms, 32); }

  // Map blob (shared payload)
  PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, huge_dir, blob_name, &blob)!=0){ perror("map blob"); return 1; }
  if(pin_prod){ pin_cpu(prod_cpu); }
  // If file provided, copy into blob at range_base and set range_len if not set
  if(file_path){
    int f = open(file_path, O_RDONLY);
    if(f<0){ perror("open file"); return 1; }
    struct stat st; if(fstat(f, &st)!=0){ perror("fstat"); close(f); return 1; }
    uint64_t fsz = (uint64_t)st.st_size;
    if(range_len==0) range_len = fsz;
    if(range_base + range_len > blob.size){ fprintf(stderr,"range exceeds blob size\n"); close(f); return 1; }
    uint8_t *dst = (uint8_t*)blob.addr + range_base;
    uint64_t left = range_len; while(left>0){ size_t chunk = left > (1<<20) ? (1<<20) : (size_t)left; ssize_t r = read(f, dst, chunk); if(r<0){ perror("read"); close(f); return 1; } if(r==0) break; dst += r; left -= (uint64_t)r; }
    close(f);
  }
  // Ensure logs dir for CSV
  (void)mkdir("logs", 0755);
  pfs_hugeblob_set_keep(&blob, 1);

  // Compute channel mapping size
  uint32_t slots = 1u<<ring_pow2; size_t ring_slots_bytes = slots * sizeof(uint32_t);
  size_t ring_hdr_bytes = (sizeof(struct pfs_fp_ring_hdr)+63)&~63u;
  size_t ring_section = ring_hdr_bytes + ring_slots_bytes + slab_bytes;
  ring_section = (ring_section + 63)&~63u;
  size_t stats_bytes = pcores * sizeof(PcoreStats);
  size_t chan_bytes = (sizeof(ChanHdr)+63)&~63u; chan_bytes += stats_bytes;
  chan_bytes = (chan_bytes + 4095)&~4095u; // 4K align
  size_t rings_base_off = chan_bytes;
  chan_bytes += (size_t)pcores * ring_section;

  // Map channel in a shared memory file (interprocess-visible)
  const char *chan_path = "/dev/shm/pfs_pcores_chan";
  int chfd = open(chan_path, O_CREAT|O_RDWR, 0600);
  if(chfd<0){ perror("open /dev/shm pcores chan"); return 1; }
  if(ftruncate(chfd, (off_t)chan_bytes)!=0){ perror("ftruncate chan"); close(chfd); return 1; }
  uint8_t *base = (uint8_t*)mmap(NULL, chan_bytes, PROT_READ|PROT_WRITE, MAP_SHARED, chfd, 0);
  if(base==MAP_FAILED){ perror("mmap chan"); close(chfd); return 1; }
  close(chfd);
  memset(base, 0, chan_bytes);

  ChanHdr *ch = (ChanHdr*)base;
  ch->ring_count=pcores; ch->ring_pow2=ring_pow2; ch->dpf=dpf; ch->align=align; ch->duration_ns=(uint64_t)(duration*1e9);
  ch->stats_off = (sizeof(ChanHdr)+63)&~63u;
  ch->rings_base_off = rings_base_off;
  ch->ring_section_bytes = ring_section; ch->slab_bytes=slab_bytes;
  PcoreStats *stats = (PcoreStats*)(base + ch->stats_off);

  // Initialize ring sections
  for(uint32_t i=0;i<pcores;i++){
    uint8_t *rs = base + ch->rings_base_off + (size_t)i * ring_section;
    struct pfs_fp_ring_hdr *hdr = (struct pfs_fp_ring_hdr*)rs; memset(hdr,0,sizeof(*hdr));
    hdr->slots = slots; hdr->mask=slots-1; hdr->head=0; hdr->tail=0; hdr->frame_size=0;
    size_t hdr_pad = (sizeof(*hdr)+63)&~63u;
    hdr->data_offset = hdr_pad + ring_slots_bytes;
    hdr->region_bytes = ring_section;
  }

  // Baseline (single-process MB/s)
  // New CPUpwn definition: compare against multi-thread CPU (threads = pcores)
  double baseline_mbs = 1.0;
  if(do_baseline){
    baseline_mbs = run_cpu_baseline_mt(blob.addr, blob.size, dpf, align, (prog_n?prog_ops[0]:op), (prog_n?prog_imms[0]:imm), baseline_s, range_base, range_len, (int)pcores);
    if(baseline_mbs <= 0.0) baseline_mbs = 1.0;
  }

  // Fork consumers
  pid_t *pids = (pid_t*)calloc(pcores, sizeof(pid_t)); if(!pids){ perror("calloc"); return 1; }
for(uint32_t i=0;i<pcores;i++){
    pid_t pid = fork();
    if(pid==0){
      int online = (int)sysconf(_SC_NPROCESSORS_ONLN);
      int span = (cpu_count>0? cpu_count : online);
      if(span<1) span=1;
      int cpu = cpu_first + (int)(i % (uint32_t)span);
      pin_cpu(cpu);
      consumer_proc(base, ch, (int)i, blob.addr, blob.size, (prog_n?prog_ops:&op), (prog_n?prog_imms:&imm), (prog_n?prog_n:1));
      _exit(0);
    } else if(pid>0){ pids[i]=pid; }
    else { perror("fork"); return 1; }
  }

  // Producer loop
  uint64_t t0=now_ns(); uint64_t next=t0+500000000ull; uint64_t produced=0; uint32_t seed=0xdeadbeef;
  // Per-ring slab write pointers
  size_t *rec_off = (size_t*)calloc(pcores, sizeof(size_t)); if(!rec_off){ perror("calloc rec_off"); return 1; }
  // Open CSV file (append)
  FILE *csv = fopen(csv_path, "a");
  if(csv){ fprintf(csv, "ts_s,pcores,bytes,mbps,frames,baseline_mbs,cpupwn\n"); fflush(csv);} 

  while(now_ns()-t0 < ch->duration_ns){
    for(uint32_t i=0;i<pcores;i++){
      uint8_t *rs = base + ch->rings_base_off + (size_t)i * ring_section;
      struct pfs_fp_ring_hdr *hdr = (struct pfs_fp_ring_hdr*)rs;
      uint32_t *slots_arr = (uint32_t*)(rs + ((sizeof(*hdr)+63)&~63u));
      uint8_t *slab = rs + hdr->data_offset;
      uint32_t head = __atomic_load_n(&hdr->head, __ATOMIC_ACQUIRE);
      uint32_t tail = __atomic_load_n(&hdr->tail, __ATOMIC_RELAXED);
      if(((tail+1)&hdr->mask) == head) continue; // full
      // write record
      uint32_t reclen = sizeof(uint32_t) + dpf*sizeof(PfsGramDesc);
      if(rec_off[i] + reclen + 64 > ch->slab_bytes) rec_off[i]=0;
      uint8_t *rec = slab + rec_off[i];
      *(uint32_t*)rec = dpf;
      PfsGramDesc *descs = (PfsGramDesc*)(rec + sizeof(uint32_t));
      for(uint32_t j=0;j<dpf;j++){
        rr32(&seed);
        uint32_t len = (seed % (align? align*4 : 4096)) + align; if(len>262144u) len=262144u;
        uint64_t rb = range_base; uint64_t rl = (range_len? range_len : blob.size);
        if (rb + rl > blob.size) rl = (rb<blob.size)? (blob.size - rb) : 0;
        if (rl == 0) { len = 0; }
        if (len > rl) len = (uint32_t)rl;
        uint64_t off = rb + (seed % (rl? rl : 1)); if(align) off &= ~((uint64_t)align-1ULL);
        if (off < rb) off = rb;
        if(off+len > rb+rl){ off = rb + rl - len; if(align) off &= ~((uint64_t)align-1ULL); if(off+len > rb+rl){ if(len>align) len=(uint32_t)align; off=rb; } }
        descs[j].offset=off; descs[j].len=len; descs[j].flags=0;
      }
      slots_arr[tail] = (uint32_t)rec_off[i];
      __atomic_store_n(&hdr->tail, (tail+1)&hdr->mask, __ATOMIC_RELEASE);
      produced++;
      rec_off[i] += (reclen + 63)&~63u;
    }
    if(now_ns()>=next){
      uint64_t total_bytes=0, total_frames=0; for(uint32_t i=0;i<pcores;i++){ total_bytes += __atomic_load_n(&stats[i].bytes_eff, __ATOMIC_RELAXED); total_frames += __atomic_load_n(&stats[i].frames, __ATOMIC_RELAXED);} 
      double secs=(now_ns()-t0)/1e9; double mb=total_bytes/1e6; double mbps=mb/secs; double cpupwn = (baseline_mbs>0.0)? (mbps / baseline_mbs) : 0.0;
      fprintf(stdout,"[proc] produced=%llu bytes=%.1f MB avg=%.1f MB/s frames=%llu CPUpwn(=%uCPU)=%.2fx\n", (unsigned long long)produced, mb, mbps, (unsigned long long)total_frames, pcores, cpupwn);
      if(csv){ fprintf(csv, "%.3f,%u,%.0f,%.3f,%llu,%.3f,%.3f\n", secs, pcores, (double)total_bytes, mbps, (unsigned long long)total_frames, baseline_mbs, cpupwn); fflush(csv);} 
      next += 500000000ull;
    }
  }

  // Wait children
  for(uint32_t i=0;i<pcores;i++){ int st=0; waitpid(pids[i], &st, 0); }
  uint64_t total_bytes=0, total_frames=0; for(uint32_t i=0;i<pcores;i++){ total_bytes += __atomic_load_n(&stats[i].bytes_eff, __ATOMIC_RELAXED); total_frames += __atomic_load_n(&stats[i].frames, __ATOMIC_RELAXED);} 
  double secs=(now_ns()-t0)/1e9; if(secs<=0) secs=1e-6; double mb=total_bytes/1e6; double mbps=mb/secs; double cpupwn = (baseline_mbs>0.0)? (mbps / baseline_mbs) : 0.0;
  fprintf(stdout,"[DONE] pcores=%u bytes=%.1f MB elapsed=%.3f s avg=%.1f MB/s frames=%llu baseline(%uCPU)=%.1f MB/s CPUpwn=%.2fx\n",
    pcores, mb, secs, mbps, (unsigned long long)total_frames, pcores, baseline_mbs, cpupwn);

  // Cleanup maps
  if(csv) fclose(csv);
  munmap(base, chan_bytes);
  pfs_hugeblob_unmap(&blob);
  return 0;
}