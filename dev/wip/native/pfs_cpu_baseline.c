// CPU baseline for PacketFS pCPU ops
// Usage:
//   dev/wip/native/pfs_cpu_baseline --size-bytes N --op checksum|xor8|add8 [--imm N]
// Output:
//   CPU_BASELINE size=... ns=... MBps=...

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

static inline uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + (uint64_t)ts.tv_nsec; }

static uint64_t fnv1a64_update(uint64_t h, const uint8_t* p, size_t n){ for(size_t i=0;i<n;i++){ h^=p[i]; h*=1099511628211ULL; } return h; }

int main(int argc, char** argv){
  uint64_t size=0; const char* op="checksum"; int imm=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--size-bytes") && i+1<argc) size=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--op") && i+1<argc) op=argv[++i];
    else if(!strcmp(argv[i],"--imm") && i+1<argc) imm=atoi(argv[++i]);
  }
  if(size==0){ fprintf(stderr,"size=0\n"); printf("CPU_BASELINE size=0 ns=0 MBps=0\n"); return 0; }

  uint8_t* buf = NULL;
  if(posix_memalign((void**)&buf, 64, size)!=0 || !buf){ printf("CPU_BASELINE size=%llu ns=0 MBps=0\n", (unsigned long long)size); return 0; }
  for(uint64_t i=0;i<size;i++) buf[i]=(uint8_t)(i);

  uint64_t t0=now_ns();
  if(!strcmp(op,"checksum")){
    volatile uint64_t h=1469598103934665603ULL; h = fnv1a64_update(h, buf, (size_t)size);
  } else if(!strcmp(op,"xor8")){
    uint8_t v=(uint8_t)(imm & 0xFF); for(uint64_t i=0;i<size;i++){ buf[i]^=v; }
  } else if(!strcmp(op,"add8")){
    uint8_t v=(uint8_t)(imm & 0xFF); for(uint64_t i=0;i<size;i++){ buf[i]=(uint8_t)(buf[i]+v); }
  } else {
    // unknown op -> checksum fallback
    volatile uint64_t h=1469598103934665603ULL; h = fnv1a64_update(h, buf, (size_t)size);
  }
  uint64_t t1=now_ns();

  double ns=(double)(t1-t0);
  double mb=(double)size/1e6;
  double mbps = ns>0.0 ? (mb/(ns/1e9)) : 0.0;
  printf("CPU_BASELINE size=%llu ns=%llu MBps=%.6f\n", (unsigned long long)size, (unsigned long long)(t1-t0), mbps);
  free(buf);
  return 0;
}

