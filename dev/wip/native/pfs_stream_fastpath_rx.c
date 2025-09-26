// SPDX-License-Identifier: MIT
// Userspace RX for /dev/pfs_fastpath shared ring; applies pCPU ops to hugeblob
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

#include "../../src/packetfs/uapi/pfs_fastpath.h"
#include "../../src/packetfs/memory/pfs_hugeblob.h"
#include "../../src/packetfs/pcpu/pfs_pcpu.h"

static uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }

int main(int argc, char **argv){
  const char *dev = "/dev/pfs_fastpath";
  size_t ring_bytes = 64ull<<20;
  double duration = 5.0;
  const char *huge_dir = "/mnt/huge1G";
  const char *blob_name = "pfs_fp_blob";
  size_t blob_size = 2ull<<30;
  const char *op_s = "xor"; uint8_t imm = 255; pfs_pcpu_op_t op = PFS_PCPU_OP_XOR_IMM8;

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dev")&&i+1<argc) dev=argv[++i];
    else if(!strcmp(argv[i],"--ring-bytes")&&i+1<argc) ring_bytes=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
    else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_size=(size_t)strtoull(argv[++i],NULL,10)<<20;
    else if(!strcmp(argv[i],"--op")&&i+1<argc) op_s=argv[++i];
    else if(!strcmp(argv[i],"--imm")&&i+1<argc) imm=(uint8_t)strtoul(argv[++i],NULL,10);
  }
  if(!strcmp(op_s,"fnv")||!strcmp(op_s,"fnv64")) op=PFS_PCPU_OP_CHECKSUM_FNV64;
  else if(!strcmp(op_s,"crc32c")) op=PFS_PCPU_OP_CHECKSUM_CRC32C;
  else if(!strcmp(op_s,"xor")) op=PFS_PCPU_OP_XOR_IMM8;
  else if(!strcmp(op_s,"add")) op=PFS_PCPU_OP_ADD_IMM8;
  else if(!strcmp(op_s,"counteq")) op=PFS_PCPU_OP_COUNT_EQ_IMM8;

  int fd = open(dev, O_RDWR|O_CLOEXEC);
  if(fd<0){ perror("open /dev/pfs_fastpath"); return 1; }
  // map (assumes setup done by TX)
  void *base = mmap(NULL, ring_bytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if(base==MAP_FAILED){ perror("mmap"); close(fd); return 1; }

  struct pfs_fp_ring_hdr *hdr = (struct pfs_fp_ring_hdr*)base;
  uint32_t *slots = (uint32_t*)((uint8_t*)base + sizeof(*hdr));
  uint8_t *slab = (uint8_t*)base + hdr->data_offset;

  // map huge blob same as TX
  PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, huge_dir, blob_name, &blob)!=0){ fprintf(stderr,"map blob failed\n"); return 1; }
  pfs_hugeblob_set_keep(&blob, 1);

  uint64_t t0=now_ns(), next=t0+500000000ull; uint64_t consumed=0; uint64_t bytes_eff=0;

  while((now_ns()-t0) < (uint64_t)(duration*1e9)){
    uint32_t head = __atomic_load_n(&hdr->head, __ATOMIC_RELAXED);
    uint32_t tail = __atomic_load_n(&hdr->tail, __ATOMIC_ACQUIRE);
    if(head == tail){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue; }
    uint32_t slot = head;
    uint32_t rec_off = slots[slot];
    // parse record
    uint8_t *rec = slab + rec_off;
    uint32_t dpf = *(uint32_t*)rec;
    PfsGramDesc *descs = (PfsGramDesc*)(rec + sizeof(uint32_t));

    // Apply pCPU op
    pfs_pcpu_metrics_t mm; memset(&mm,0,sizeof(mm));
    (void)pfs_pcpu_apply(blob.addr, blob.size, descs, dpf, op, imm, 1469598103934665603ULL, &mm);
    bytes_eff += mm.bytes_touched;

    __atomic_store_n(&hdr->head, (head+1)&hdr->mask, __ATOMIC_RELEASE);
    consumed++;

    if(now_ns()>=next){
      double secs=(now_ns()-t0)/1e9; fprintf(stdout,"[fp-rx] consumed=%llu bytes_eff=%.1f MB avg=%.1f MB/s\n",
        (unsigned long long)consumed, bytes_eff/1e6, (bytes_eff/1e6)/secs);
      next += 500000000ull;
    }
  }

  munmap(base, ring_bytes); close(fd);
  pfs_hugeblob_unmap(&blob);
  return 0;
}