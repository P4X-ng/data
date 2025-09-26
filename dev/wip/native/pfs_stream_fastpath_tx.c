// SPDX-License-Identifier: MIT
// Userspace TX for /dev/pfs_fastpath shared ring (prototype)
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
#include "../../src/packetfs/gram/pfs_gram.h"

static uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }

static inline uint32_t rr32(uint32_t *x){ *x ^= *x>>13; *x ^= *x<<17; *x ^= *x>>5; return *x; }

int main(int argc, char **argv){
  const char *dev = "/dev/pfs_fastpath";
  size_t ring_bytes = 64ull<<20; // 64 MiB
  double duration = 5.0;
  const char *huge_dir = "/mnt/huge1G";
  const char *blob_name = "pfs_fp_blob";
  size_t blob_size = 2ull<<30; // 2 GiB
  uint32_t dpf = 64; uint32_t align=64;

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--dev")&&i+1<argc) dev=argv[++i];
    else if(!strcmp(argv[i],"--ring-bytes")&&i+1<argc) ring_bytes=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--duration")&&i+1<argc) duration=strtod(argv[++i],NULL);
    else if(!strcmp(argv[i],"--blob-mb")&&i+1<argc) blob_size=(size_t)strtoull(argv[++i],NULL,10)<<20;
    else if(!strcmp(argv[i],"--dpf")&&i+1<argc) dpf=(uint32_t)strtoul(argv[++i],NULL,10);
  }

  int fd = open(dev, O_RDWR|O_CLOEXEC);
  if(fd<0){ perror("open /dev/pfs_fastpath"); return 1; }
  struct pfs_fp_setup s = { .ring_bytes = (uint32_t)ring_bytes, .flags=0 };
  if(ioctl(fd, PFS_FP_IOC_SETUP, &s)!=0){ perror("ioctl SETUP"); close(fd); return 1; }

  void *base = mmap(NULL, ring_bytes, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
  if(base==MAP_FAILED){ perror("mmap"); close(fd); return 1; }

  struct pfs_fp_ring_hdr *hdr = (struct pfs_fp_ring_hdr*)base;
  uint32_t *slots = (uint32_t*)((uint8_t*)base + sizeof(*hdr));
  uint8_t *slab = (uint8_t*)base + hdr->data_offset;
  size_t slab_bytes = hdr->region_bytes - hdr->data_offset;

  // Huge blob backing for synthetic descriptors
  PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, huge_dir, blob_name, &blob)!=0){ fprintf(stderr,"map blob failed\n"); return 1; }
  pfs_hugeblob_set_keep(&blob, 1);

  uint64_t t0 = now_ns(); uint64_t next = t0 + 500000000ull;
  uint32_t x=0x1234abcd; uint64_t produced=0;
  size_t rec_off = 0; // bump pointer into slab for records

  while((now_ns()-t0) < (uint64_t)(duration*1e9)){
    // Space check
    uint32_t head = __atomic_load_n(&hdr->head, __ATOMIC_ACQUIRE);
    uint32_t tail = __atomic_load_n(&hdr->tail, __ATOMIC_RELAXED);
    uint32_t n = hdr->slots; if(((tail+1)&hdr->mask)==head){ // full
      // backoff
      struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue;
    }

    // Build a tiny record of PfsGramDesc in the slab
    uint32_t rec_len = sizeof(uint32_t) + dpf * sizeof(PfsGramDesc);
    if(rec_off + rec_len + 64 > slab_bytes) rec_off = 0; // wrap slab
    uint8_t *rec = slab + rec_off;
    *(uint32_t*)rec = dpf;
    PfsGramDesc *descs = (PfsGramDesc*)(rec + sizeof(uint32_t));
    uint64_t base_off = blob.size/2;
    uint64_t prev_off = base_off;
    for(uint32_t i=0;i<dpf;i++){
      rr32(&x);
      uint32_t len = (x % (align? align*4 : 4096)) + align;
      if(len > 262144u) len = 262144u;
      uint64_t off = (x % (blob.size?blob.size:1));
      if(align) off &= ~((uint64_t)align-1ULL);
      if(off + len > blob.size){ if(len > blob.size) len = (uint32_t)blob.size; off = blob.size - len; if(align) off &= ~((uint64_t)align-1ULL); }
      // absolute offsets for simplicity
      descs[i].offset = off; descs[i].len = len; descs[i].flags = 0;
      prev_off = off;
    }

    // Publish rec offset (relative to slab base) into slot
    uint32_t slot = tail;
    slots[slot] = (uint32_t)rec_off; // consumer finds record at slab+off
    __atomic_store_n(&hdr->tail, (tail+1)&hdr->mask, __ATOMIC_RELEASE);

    produced++;
    rec_off += (rec_len + 63) & ~63u;

    if(now_ns()>=next){
      double secs = (now_ns()-t0)/1e9; fprintf(stdout,"[fp-tx] produced=%llu slots=%u secs=%.3f\n", (unsigned long long)produced, hdr->slots, secs);
      next += 500000000ull;
    }
  }

  munmap(base, ring_bytes); close(fd);
  pfs_hugeblob_unmap(&blob);
  return 0;
}