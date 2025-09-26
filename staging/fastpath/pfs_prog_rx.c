// SPDX-License-Identifier: MIT
// staging/fastpath/pfs_prog_rx.c
// Parse program-carrying records from /dev/pfs_fastpath slab and apply them over the blob.
// Record layout:
//   [PfsInsnHdr][PfsInsn[n]][u32 dpf][PfsGramDesc[dpf]]

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
#include "../../src/packetfs/pcpu/pfs_pcpu.h"

static uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }
static void pin_cpu(int cpu){
  if(cpu<0) return; cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu,&set); sched_setaffinity(0,sizeof(set),&set);
}

static size_t map_insns_to_pcpu(const PfsInsn *ins, size_t n, pfs_pcpu_op_t *ops, uint8_t *imms, size_t max){
  size_t k=0; for(size_t i=0;i<n && k<max;i++){
    pfs_pcpu_op_t op=PFS_PCPU_OP_XOR_IMM8; uint8_t imm=(uint8_t)ins[i].imm;
    switch(ins[i].opcode){
      case PFSI_MOVI:   op=PFS_PCPU_OP_ADD_IMM8; break; // MOVI maps to add imm on bytes (illustrative)
      case PFSI_ADD:    op=PFS_PCPU_OP_ADD_IMM8; break;
      case PFSI_SUB:    op=PFS_PCPU_OP_ADD_IMM8; imm=(uint8_t)(-((int)imm)); break;
      case PFSI_MUL:    op=PFS_PCPU_OP_HIST8; imm=0; break; // use HIST8 as placeholder reduction
      case PFSI_ADDI:   op=PFS_PCPU_OP_ADD_IMM8; break;
      default:          op=PFS_PCPU_OP_XOR_IMM8; break;
    }
    ops[k]=op; imms[k]=imm; k++;
  }
  return k;
}

int main(int argc, char **argv){
  const char *dev="/dev/pfs_fastpath";
  size_t ring_bytes=64ull<<20; double duration=5.0;
  const char *huge_dir="/mnt/huge1G"; const char *blob_name="pfs_prog_blob"; size_t blob_size=2ull<<30;

int pin = -1;
for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dev")&&i+1<argc) dev=argv[++i];
    else if(!strcmp(argv[i],"--ring-bytes")&&i+1<argc) ring_bytes=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_size=(size_t)strtoull(argv[++i],NULL,10)<<20;
else if(!strcmp(argv[i],"--cpu")&&i+1<argc) pin=(int)strtol(argv[++i],NULL,10);
  }

if(pin>=0) pin_cpu(pin);
int fd=open(dev,O_RDWR|O_CLOEXEC); if(fd<0){ perror("open /dev/pfs_fastpath"); return 1; }
  void *base=mmap(NULL, ring_bytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if(base==MAP_FAILED){ perror("mmap"); close(fd); return 1; }

  struct pfs_fp_ring_hdr *hdr=(struct pfs_fp_ring_hdr*)base;
  uint32_t *slots=(uint32_t*)((uint8_t*)base + sizeof(*hdr));
  uint8_t *slab=(uint8_t*)base + hdr->data_offset;

  PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, huge_dir, blob_name, &blob)!=0){ fprintf(stderr,"map blob failed\n"); return 1; }
  pfs_hugeblob_set_keep(&blob,1);

  uint64_t t0=now_ns(), next=t0+500000000ull; uint64_t consumed=0, bytes_eff=0;

  while((now_ns()-t0) < (uint64_t)(duration*1e9)){
    uint32_t head = __atomic_load_n(&hdr->head, __ATOMIC_RELAXED);
    uint32_t tail = __atomic_load_n(&hdr->tail, __ATOMIC_ACQUIRE);
    if(head==tail){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue; }

    uint32_t off = slots[head];
    uint8_t *rec = slab + off; size_t pos=0;

    // Parse header
    if((size_t)(rec + sizeof(PfsInsnHdr)) > (size_t)(slab + hdr->region_bytes)) { __atomic_store_n(&hdr->head,(head+1)&hdr->mask,__ATOMIC_RELEASE); continue; }
    PfsInsnHdr ih; memcpy(&ih, rec+pos, sizeof(ih)); pos += sizeof(ih);
    if(ih.magic != PFSI_MAGIC || ih.version != 1){ __atomic_store_n(&hdr->head,(head+1)&hdr->mask,__ATOMIC_RELEASE); continue; }

    // Parse insns
    PfsInsn ins[64]; if(ih.insn_count > 64) ih.insn_count = 64;
    memcpy(ins, rec+pos, ih.insn_count * sizeof(PfsInsn)); pos += ih.insn_count*sizeof(PfsInsn);

    // dpf
    uint32_t dpf; memcpy(&dpf, rec+pos, sizeof(dpf)); pos += sizeof(uint32_t);

    // descs
    PfsGramDesc *descs = (PfsGramDesc*)(rec+pos);

    // Map to pCPU ops
    pfs_pcpu_op_t ops[64]; uint8_t imms[64]; size_t nops = map_insns_to_pcpu(ins, ih.insn_count, ops, imms, 64);
    if(nops==0){ // default to XOR
      ops[0]=PFS_PCPU_OP_XOR_IMM8; imms[0]=255; nops=1; }

    // Apply
    uint64_t touched=0; for(size_t k=0;k<nops;k++){ pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm)); (void)pfs_pcpu_apply(blob.addr, blob.size, descs, dpf, ops[k], imms[k], 1469598103934665603ULL, &mm); touched += mm.bytes_touched; }

    bytes_eff += touched; consumed++;
    __atomic_store_n(&hdr->head, (head+1)&hdr->mask, __ATOMIC_RELEASE);

    if(now_ns()>=next){ double secs=(now_ns()-t0)/1e9; fprintf(stdout,"[prog-rx] recs=%llu bytes=%.1f MB avg=%.1f MB/s\n", (unsigned long long)consumed, bytes_eff/1e6, (bytes_eff/1e6)/secs); next += 500000000ull; }
  }

  munmap(base, ring_bytes); close(fd); pfs_hugeblob_unmap(&blob);
  return 0;
}
