// pfs_scan_agent.c — in-guest consumer skeleton for scan tasks
// Maps an existing ring-backed file (or ivshmem-mapped region exposed as a file),
// pulls records, and prints task summaries. Replace the inner loop with AF_PACKET
// transmit logic to turn this into a working scanner.

#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#include "pfs_scan_ring.h"

static inline uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }

int main(int argc,char**argv){
  const char* path = "/dev/shm/pfs_scan_ring.bin";
  size_t region_bytes = 64ull<<20;

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--path")&&i+1<argc) path=argv[++i];
    else if(!strcmp(argv[i],"--region-bytes")&&i+1<argc) region_bytes=(size_t)strtoull(argv[++i],NULL,10);
  }

  int fd = open(path, O_RDWR);
  if(fd<0){ perror("open ring file"); return 1; }
  void* base = mmap(NULL,region_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
  if(base==MAP_FAILED){ perror("mmap"); return 1; }
  RingHdr* hdr=(RingHdr*)base;
  uint32_t* slotv = (uint32_t*)((uint8_t*)base + sizeof(RingHdr));
  uint8_t* slab = (uint8_t*)base + hdr->data_offset;

  uint64_t t0=now_ns(), next=t0+500000000ull; uint64_t consumed=0, tasks=0;
  while(1){
    uint32_t head = __atomic_load_n(&hdr->head,__ATOMIC_RELAXED);
    uint32_t tail = __atomic_load_n(&hdr->tail,__ATOMIC_ACQUIRE);
    if(head==tail){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); goto tick; }
    uint32_t slot=head; uint32_t off=slotv[slot];
    uint8_t* rec = slab + off; uint32_t n = *(uint32_t*)rec;
    ScanTask* t = (ScanTask*)(rec+sizeof(uint32_t));

    // TODO: Replace with AF_PACKET transmit + minimal checksum updates
    // For now, just count
    tasks += n; consumed++;

    __atomic_store_n(&hdr->head,(head+1)&hdr->mask,__ATOMIC_RELEASE);
  tick:
    if(now_ns()>=next){
      double secs=(now_ns()-t0)/1e9; fprintf(stdout,"[agent] consumed=%llu tasks=%llu avg_tasks_per_s=%.1f\n",
        (unsigned long long)consumed,(unsigned long long)tasks, tasks/secs);
      next+=500000000ull;
    }
  }
}
