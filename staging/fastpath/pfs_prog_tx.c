// SPDX-License-Identifier: MIT
// staging/fastpath/pfs_prog_tx.c
// Build program-carrying records and publish them into /dev/pfs_fastpath.
// Record layout in slab:
//   [PfsInsnHdr][PfsInsn[insn_count]][u32 dpf][PfsGramDesc[dpf]]

#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/ioctl.h>
#include <time.h>
#include <sched.h>

#include "../../src/packetfs/uapi/pfs_fastpath.h"
#include "../../src/packetfs/memory/pfs_hugeblob.h"
#include "../../src/packetfs/gram/pfs_gram.h"
#include "../../src/packetfs/gram/pfs_insn.h"

static uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }
static void pin_cpu(int cpu){ if(cpu<0) return; cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu,&set); sched_setaffinity(0,sizeof(set),&set);}
static inline uint32_t rr32(uint32_t *x){ *x ^= *x>>13; *x ^= *x<<17; *x ^= *x>>5; return *x; }

static size_t parse_prog(const char *s, PfsInsn *out, size_t max_n){
  if(!s||!*s) return 0;
  char *dup=strdup(s); if(!dup) return 0;
  size_t n=0; char *save=NULL; char *tok=strtok_r(dup, ",", &save);
  while(tok && n<max_n){
    char *name=tok; char *colon=strchr(tok, ':'); unsigned long v=0;
    if(colon){ *colon='\0'; v=strtoul(colon+1,NULL,0); }
    memset(&out[n],0,sizeof(out[n]));
    if(!strcmp(name,"mov")||!strcmp(name,"movi")) { out[n].opcode=PFSI_MOVI; out[n].imm=(uint32_t)v; }
    else if(!strcmp(name,"add")) { out[n].opcode=PFSI_ADD; out[n].imm=(uint32_t)v; }
    else if(!strcmp(name,"sub")) { out[n].opcode=PFSI_SUB; out[n].imm=(uint32_t)v; }
    else if(!strcmp(name,"mul")) { out[n].opcode=PFSI_MUL; out[n].imm=(uint32_t)v; }
    else if(!strcmp(name,"addi")) { out[n].opcode=PFSI_ADDI; out[n].imm=(uint32_t)v; }
    else if(!strcmp(name,"xor")) { out[n].opcode=PFSI_ADDI; out[n].imm=(uint32_t)(v ^ 0); } // map to ADDI semantics; interpreter translates to XOR op later
    else if(!strcmp(name,"counteq")) { out[n].opcode=PFSI_ADDI; out[n].imm=(uint32_t)v; }
    else if(!strcmp(name,"crc32c")) { out[n].opcode=PFSI_ADDI; out[n].imm=0; }
    else if(!strcmp(name,"fnv")||!strcmp(name,"fnv64")) { out[n].opcode=PFSI_ADDI; out[n].imm=0; }
    else { tok=strtok_r(NULL, ",", &save); continue; }
    n++; tok=strtok_r(NULL, ",", &save);
  }
  free(dup); return n;
}

int main(int argc, char **argv){
  const char *dev="/dev/pfs_fastpath";
  size_t ring_bytes=64ull<<20; // 64 MiB
  double duration=5.0;
  const char *huge_dir="/mnt/huge1G"; const char *blob_name="pfs_prog_blob"; size_t blob_size=2ull<<30;
  uint32_t dpf=64; uint32_t align=64; const char *prog_s="xor:255"; // default simple op

int pin=-1;
for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dev")&&i+1<argc) dev=argv[++i];
    else if(!strcmp(argv[i],"--ring-bytes")&&i+1<argc) ring_bytes=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
    else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_size=(size_t)strtoull(argv[++i],NULL,10)<<20;
    else if(!strcmp(argv[i],"--dpf")&&i+1<argc) dpf=(uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--align")&&i+1<argc) align=(uint32_t)strtoul(argv[++i],NULL,10);
else if(!strcmp(argv[i],"--prog")&&i+1<argc) prog_s=argv[++i];
else if(!strcmp(argv[i],"--cpu")&&i+1<argc) pin=(int)strtol(argv[++i],NULL,10);
  }

  // Prepare program
  PfsInsn insns[32]; size_t insn_n = parse_prog(prog_s, insns, 32);
  if(insn_n==0){ fprintf(stderr,"no program ops (use --prog)\n"); return 2; }

if(pin>=0) pin_cpu(pin);
int fd=open(dev,O_RDWR|O_CLOEXEC); if(fd<0){ perror("open /dev/pfs_fastpath"); return 1; }
  struct pfs_fp_setup s={ .ring_bytes=(uint32_t)ring_bytes, .flags=0};
  if(ioctl(fd,PFS_FP_IOC_SETUP,&s)!=0){ perror("ioctl SETUP"); close(fd); return 1; }

  void *base=mmap(NULL, ring_bytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if(base==MAP_FAILED){ perror("mmap"); close(fd); return 1; }

  struct pfs_fp_ring_hdr *hdr=(struct pfs_fp_ring_hdr*)base;
  uint32_t *slots=(uint32_t*)((uint8_t*)base + sizeof(*hdr));
  uint8_t *slab=(uint8_t*)base + hdr->data_offset;
  size_t slab_bytes = hdr->region_bytes - hdr->data_offset;

  PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, huge_dir, blob_name, &blob)!=0){ fprintf(stderr,"map blob failed\n"); return 1; }
  pfs_hugeblob_set_keep(&blob,1);

  uint64_t t0=now_ns(), next=t0+500000000ull; uint64_t produced=0; size_t rec_off=0; uint32_t x=0x13572468; uint64_t seq=0;

  while((now_ns()-t0) < (uint64_t)(duration*1e9)){
    uint32_t head = __atomic_load_n(&hdr->head, __ATOMIC_ACQUIRE);
    uint32_t tail = __atomic_load_n(&hdr->tail, __ATOMIC_RELAXED);
    if(((tail+1)&hdr->mask)==head){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue; }

    // Build record: [PfsInsnHdr][insns][u32 dpf][PfsGramDesc[dpf]]
    size_t need = sizeof(PfsInsnHdr) + insn_n*sizeof(PfsInsn) + sizeof(uint32_t) + dpf*sizeof(PfsGramDesc);
    if(rec_off + need + 64 > slab_bytes) rec_off=0;

    uint8_t *rec = slab + rec_off; size_t pos=0;
    PfsInsnHdr ih; pfsi_header_write(&ih, seq++, (uint16_t)insn_n);
    memcpy(rec+pos, &ih, sizeof(ih)); pos += sizeof(ih);
    memcpy(rec+pos, insns, insn_n*sizeof(PfsInsn)); pos += insn_n*sizeof(PfsInsn);
    *(uint32_t*)(rec+pos) = dpf; pos += sizeof(uint32_t);

    PfsGramDesc *descs = (PfsGramDesc*)(rec+pos);
    for(uint32_t i=0;i<dpf;i++){
      rr32(&x);
      uint32_t len = (x % (align? align*4 : 4096)) + align; if(len>262144u) len=262144u;
      uint64_t off = (x % (blob.size?blob.size:1)); if(align) off &= ~((uint64_t)align-1ULL);
      if(off+len>blob.size){ if(len>blob.size) len=(uint32_t)blob.size; off=blob.size-len; if(align) off &= ~((uint64_t)align-1ULL);} 
      descs[i].offset=off; descs[i].len=len; descs[i].flags=0;
    }
    pos += dpf*sizeof(PfsGramDesc);

    slots[tail] = (uint32_t)rec_off;
    __atomic_store_n(&hdr->tail, (tail+1)&hdr->mask, __ATOMIC_RELEASE);
    produced++;
    rec_off += (pos + 63) & ~63ULL;

    if(now_ns()>=next){ double secs=(now_ns()-t0)/1e9; fprintf(stdout,"[prog-tx] recs=%llu insn_n=%zu mb=%.1f\n", (unsigned long long)produced, insn_n, (double)(produced * need)/1e6); next += 500000000ull; }
  }

  munmap(base, ring_bytes); close(fd); pfs_hugeblob_unmap(&blob);
  return 0;
}
