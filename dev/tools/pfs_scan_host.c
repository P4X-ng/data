// pfs_scan_host.c — host-side producer/collector skeleton for scan tasks
// Creates/initializes a ring-backed file, publishes ScanTask batches from a CIDR, and
// (optionally) reads results from a second ring. This is a skeleton for ivshmem bring-up.

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

static int parse_cidr(const char* s, uint32_t* out_base, uint32_t* out_count){
  // Supports IPv4 CIDR a.b.c.d/nn only
  char ip[64]; strncpy(ip,s,sizeof(ip)); ip[sizeof(ip)-1]='\0';
  char* slash = strchr(ip,'/'); if(!slash) return -1; *slash='\0';
  int prefix = atoi(slash+1); if(prefix<0||prefix>32) return -1;
  struct in_addr a; if(inet_aton(ip,&a)==0) return -1;
  uint32_t base = ntohl(a.s_addr);
  uint32_t mask = prefix==0 ? 0 : (~0u << (32-prefix));
  base &= mask;
  uint32_t count = prefix==32 ? 1 : (1u << (32-prefix));
  *out_base = base; *out_count = count; return 0;
}

int main(int argc,char**argv){
  const char* path = "/dev/shm/pfs_scan_ring.bin";
  const char* cidr = "192.0.2.0/24"; // example network
  uint16_t port = 80; uint8_t proto = 6; // TCP
  uint32_t slots_pow2 = 12; // 4096 slots
  uint32_t batch = 64; // tasks per record
  size_t region_bytes = 64ull<<20; // 64 MiB

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--path")&&i+1<argc) path=argv[++i];
    else if(!strcmp(argv[i],"--cidr")&&i+1<argc) cidr=argv[++i];
    else if(!strcmp(argv[i],"--port")&&i+1<argc) port=(uint16_t)atoi(argv[++i]);
    else if(!strcmp(argv[i],"--proto")&&i+1<argc) proto=(uint8_t)atoi(argv[++i]);
    else if(!strcmp(argv[i],"--slots-pow2")&&i+1<argc) slots_pow2=(uint32_t)atoi(argv[++i]);
    else if(!strcmp(argv[i],"--batch")&&i+1<argc) batch=(uint32_t)atoi(argv[++i]);
    else if(!strcmp(argv[i],"--region-bytes")&&i+1<argc) region_bytes=(size_t)strtoull(argv[++i],NULL,10);
  }

  int fd = open(path, O_CREAT|O_RDWR, 0666);
  if(fd<0){ perror("open ring file"); return 1; }
  if(ftruncate(fd, (off_t)region_bytes)!=0){ perror("ftruncate"); return 1; }
  void* base = mmap(NULL,region_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
  if(base==MAP_FAILED){ perror("mmap"); return 1; }
  RingHdr* hdr=(RingHdr*)base;
  uint32_t slots=1u<<slots_pow2; hdr->slots=slots; hdr->mask=slots-1; hdr->head=0; hdr->tail=0;
  uint32_t slots_bytes = slots * sizeof(uint32_t);
  hdr->data_offset = sizeof(RingHdr) + slots_bytes;
  hdr->region_bytes = (uint32_t)region_bytes;
  uint32_t* slotv = (uint32_t*)((uint8_t*)base + sizeof(RingHdr));
  uint8_t* slab = (uint8_t*)base + hdr->data_offset;
  size_t slab_cap = region_bytes - hdr->data_offset;

  uint32_t ip_base=0, ip_count=0; if(parse_cidr(cidr,&ip_base,&ip_count)!=0){ fprintf(stderr,"bad cidr\n"); return 1; }

  uint64_t t0=now_ns(), next=t0+500000000ull; uint64_t produced=0; size_t rec_off=0; uint64_t tasks_total=0;
  for(uint32_t idx=0; idx<ip_count;){
    // space check
    uint32_t head = __atomic_load_n(&hdr->head,__ATOMIC_ACQUIRE);
    uint32_t tail = __atomic_load_n(&hdr->tail,__ATOMIC_RELAXED);
    if(((tail+1)&hdr->mask)==head){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue; }
    // record len
    uint32_t n = (idx+batch<=ip_count)? batch : (ip_count-idx);
    uint32_t rec_len = sizeof(uint32_t) + n*sizeof(ScanTask);
    if(rec_off + rec_len + 64 > slab_cap) rec_off = 0; // wrap
    uint8_t* rec = slab + rec_off; *(uint32_t*)rec = n;
    ScanTask* t = (ScanTask*)(rec + sizeof(uint32_t));
    for(uint32_t i=0;i<n;i++){
      uint32_t ip = (ip_base + idx + i);
      uint32_t le = htonl(ip); // store network order for readability
      t[i].dst_ipv4 = le; t[i].port = htons(port); t[i].proto = proto; t[i].pad=0;
    }
    // publish
    slotv[tail] = (uint32_t)rec_off;
    __atomic_store_n(&hdr->tail,(tail+1)&hdr->mask,__ATOMIC_RELEASE);
    produced++; tasks_total += n; idx += n; rec_off += (rec_len + 63) & ~63u;

    if(now_ns()>=next){
      double secs=(now_ns()-t0)/1e9; fprintf(stdout,"[host] produced=%llu tasks=%llu avg_tasks_per_s=%.1f\n",
        (unsigned long long)produced, (unsigned long long)tasks_total, tasks_total/secs);
      next += 500000000ull;
    }
  }

  fprintf(stdout,"[host DONE] tasks=%llu\n", (unsigned long long)tasks_total);
  munmap(base,region_bytes); close(fd); return 0;
}
