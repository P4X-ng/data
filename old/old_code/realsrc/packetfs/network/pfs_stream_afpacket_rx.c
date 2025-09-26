#define _GNU_SOURCE
#include <errno.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <linux/if_packet.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>
#include <sched.h>

static void usage(const char* prog){
  fprintf(stderr,
    "Usage: %s --ifname IF [--frame-size N] [--duration S] [--cpu N] [--pcpu-op fnv|xor|add|crc32c|counteq] [--imm N]\n",
    prog);
}

static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void set_affinity(int cpu){ if(cpu<0) return; cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu,&set); sched_setaffinity(0,sizeof(set),&set); }
static unsigned long long fnv1a64(const unsigned char* p, size_t n){ unsigned long long h=1469598103934665603ULL; for(size_t i=0;i<n;i++){ h^=p[i]; h*=1099511628211ULL; } return h; }
static void apply_op(unsigned char* p, size_t n, const char* op, unsigned imm, unsigned long long* acc){
  if(!op) return; if(!strcmp(op,"xor")){ for(size_t i=0;i<n;i++) p[i]^=(unsigned char)imm; }
  else if(!strcmp(op,"add")){ for(size_t i=0;i<n;i++) p[i]=(unsigned char)(p[i]+(unsigned char)imm); }
  else if(!strcmp(op,"fnv")||!strcmp(op,"fnv64")){ if(acc) *acc^=fnv1a64(p,n); }
  else if(!strcmp(op,"counteq")){ unsigned long long c=0; unsigned char v=(unsigned char)imm; for(size_t i=0;i<n;i++) c+=(p[i]==v); if(acc) *acc^=c; }
}

int main(int argc, char** argv){
  const char* ifname=NULL; size_t frame_sz=4096; double duration=10.0; int cpu=-1; const char* pcpu_op=NULL; unsigned imm=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i], "--ifname") && i+1<argc) ifname=argv[++i];
    else if(!strcmp(argv[i], "--frame-size") && i+1<argc) frame_sz=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i], "--duration") && i+1<argc) duration=strtod(argv[++i],NULL);
    else if(!strcmp(argv[i], "--cpu") && i+1<argc) cpu=atoi(argv[++i]);
    else if(!strcmp(argv[i], "--pcpu-op") && i+1<argc) pcpu_op=argv[++i];
    else if(!strcmp(argv[i], "--imm") && i+1<argc) imm=(unsigned)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i], "-h")||!strcmp(argv[i], "--help")) { usage(argv[0]); return 0; }
  }
  if(!ifname){ usage(argv[0]); return 2; }

  set_affinity(cpu);
  int ifindex = if_nametoindex(ifname); if(ifindex==0){ perror("if_nametoindex"); return 2; }
  int fd = socket(AF_PACKET, SOCK_RAW, htons(0x88B5)); if(fd<0){ perror("socket(AF_PACKET)"); return 2; }

  struct sockaddr_ll sll; memset(&sll,0,sizeof(sll)); sll.sll_family=AF_PACKET; sll.sll_protocol=htons(0x88B5); sll.sll_ifindex=ifindex;
  if(bind(fd,(struct sockaddr*)&sll,sizeof(sll))<0){ perror("bind"); close(fd); return 2; }

  unsigned char* buf = (unsigned char*)malloc(frame_sz); if(!buf){ perror("malloc"); close(fd); return 2; }

  double t0=now_sec(), tlast=t0; unsigned long long bytes=0, pkts=0, acc=0;
  while((now_sec()-t0)<duration){
    ssize_t n = recv(fd, buf, frame_sz, 0);
    if(n<0){ if(errno==EINTR) continue; if(errno==EAGAIN) continue; perror("recv"); break; }
    // Apply arithmetic if asked (skip L2)
    size_t l2 = sizeof(struct ether_header); if(n > (ssize_t)l2 && pcpu_op) apply_op(buf+l2, (size_t)(n - (ssize_t)l2), pcpu_op, imm, &acc);
    bytes += (unsigned long long)n; pkts++;
    if((now_sec()-tlast) >= 1.0){ double dt=now_sec()-t0; double mbps=(bytes/1e6)/dt; fprintf(stderr,"[RX] pkts=%llu bytes=%llu MB/s=%.1f acc=%llx\n", pkts, bytes, mbps, acc); tlast=now_sec(); }
  }
  double dt=now_sec()-t0; double mbps = dt>0 ? (bytes/1e6)/dt : 0.0;
  fprintf(stderr, "[RX DONE] pkts=%llu bytes=%llu time=%.3f s MB/s=%.1f acc=%llx\n", pkts, bytes, dt, mbps, acc);
  free(buf); close(fd); return 0;
}
