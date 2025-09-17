#define _GNU_SOURCE
#include <errno.h>
#include <net/ethernet.h>
#include <net/if.h>
#include <linux/if_packet.h>
#include <arpa/inet.h>
#include <netinet/in.h>
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
    "Usage: %s --ifname IF --dst MAC [--frame-size N] [--duration S] [--blob-size B] [--align A] [--cpu N] [--pcpu-op fnv|xor|add|crc32c|counteq] [--imm N]\n",
    prog);
}

static int hex2byte(const char* s){ int x; if(sscanf(s, "%x", &x)!=1) return -1; return x & 0xFF; }

static int parse_mac(const char* str, unsigned char mac[6]){
  char buf[64]; strncpy(buf, str, sizeof(buf)); buf[sizeof(buf)-1]='\0';
  char* p = buf; for(int i=0;i<6;i++){
    char* q = (i<5) ? strchr(p, ':') : NULL; if(q) *q='\0';
    int b = hex2byte(p); if(b<0) return -1; mac[i]=(unsigned char)b;
    if(!q) break; p = q+1;
  }
  return 0;
}

static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void set_affinity(int cpu){
  if(cpu < 0) return; cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set); sched_setaffinity(0, sizeof(set), &set);
}

static unsigned long long fnv1a64(const unsigned char* p, size_t n){
  unsigned long long h = 1469598103934665603ULL; for(size_t i=0;i<n;i++){ h ^= p[i]; h *= 1099511628211ULL; } return h;
}

static void apply_op(unsigned char* p, size_t n, const char* op, unsigned imm, unsigned long long* acc){
  if(!op) return;
  if(!strcmp(op, "xor")){
    for(size_t i=0;i<n;i++) p[i] ^= (unsigned char)imm;
  } else if(!strcmp(op, "add")){
    for(size_t i=0;i<n;i++) p[i] = (unsigned char)(p[i] + (unsigned char)imm);
  } else if(!strcmp(op, "fnv")||!strcmp(op, "fnv64")){
    if(acc) *acc ^= fnv1a64(p, n);
  } else if(!strcmp(op, "counteq")){
    unsigned long long c = 0; unsigned char v=(unsigned char)imm; for(size_t i=0;i<n;i++) c += (p[i]==v); if(acc) *acc ^= c;
  } else if(!strcmp(op, "crc32c")){
    // Placeholder: real CRC32C would use hw accel or a table; skip to keep hot loop light.
  }
}

int main(int argc, char** argv){
  const char* ifname = NULL; const char* dst_str = "ff:ff:ff:ff:ff:ff";
  size_t frame_sz = 4096; double duration = 10.0; int cpu=-1; const char* pcpu_op=NULL; unsigned imm=0;
  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i], "--ifname") && i+1<argc) ifname=argv[++i];
    else if(!strcmp(argv[i], "--dst") && i+1<argc) dst_str=argv[++i];
    else if(!strcmp(argv[i], "--frame-size") && i+1<argc) frame_sz=strtoull(argv[++i],NULL,10);
    else if(!strcmp(argv[i], "--duration") && i+1<argc) duration=strtod(argv[++i],NULL);
    else if(!strcmp(argv[i], "--cpu") && i+1<argc) cpu=atoi(argv[++i]);
    else if(!strcmp(argv[i], "--pcpu-op") && i+1<argc) pcpu_op=argv[++i];
    else if(!strcmp(argv[i], "--imm") && i+1<argc) imm=(unsigned)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i], "-h")||!strcmp(argv[i], "--help")) { usage(argv[0]); return 0; }
  }
  if(!ifname){ usage(argv[0]); return 2; }

  set_affinity(cpu);
  if(!ifname){ usage(argv[0]); return 2; }

  int ifindex = if_nametoindex(ifname); if(ifindex==0){ perror("if_nametoindex"); return 2; }

  int fd = socket(AF_PACKET, SOCK_RAW, htons(0x88B5)); if(fd<0){ perror("socket(AF_PACKET)"); return 2; }

  // Fetch src MAC
  unsigned char src_mac[6]; struct ifreq ifr; memset(&ifr,0,sizeof(ifr)); strncpy(ifr.ifr_name, ifname, sizeof(ifr.ifr_name)-1);
  if(ioctl(fd, SIOCGIFHWADDR, &ifr)<0){ perror("SIOCGIFHWADDR"); close(fd); return 2; }
  memcpy(src_mac, ifr.ifr_hwaddr.sa_data, 6);

  unsigned char dst_mac[6]; if(parse_mac(dst_str, dst_mac)<0){ fprintf(stderr, "bad dst mac: %s\n", dst_str); close(fd); return 2; }

  // Bind to interface
  struct sockaddr_ll sll; memset(&sll,0,sizeof(sll)); sll.sll_family = AF_PACKET; sll.sll_protocol = htons(0x88B5); sll.sll_ifindex = ifindex;
  if(bind(fd, (struct sockaddr*)&sll, sizeof(sll))<0){ perror("bind(AF_PACKET)"); close(fd); return 2; }

  // Build a frame buffer
  if(frame_sz < sizeof(struct ether_header)+16) frame_sz = sizeof(struct ether_header)+16;
  unsigned char* buf = (unsigned char*)malloc(frame_sz); if(!buf){ perror("malloc"); close(fd); return 2; }
  struct ether_header* eh = (struct ether_header*)buf;
  memcpy(eh->ether_dhost, dst_mac, 6); memcpy(eh->ether_shost, src_mac, 6); eh->ether_type = htons(0x88B5);
  // Payload pattern baseline
  for(size_t i=sizeof(*eh); i<frame_sz; i++) buf[i] = (unsigned char)(i & 0xFF);

  // Destination sockaddr_ll
  struct sockaddr_ll to; memset(&to,0,sizeof(to)); to.sll_family=AF_PACKET; to.sll_ifindex=ifindex; to.sll_halen=6; memcpy(to.sll_addr, dst_mac, 6);

  double t0 = now_sec(); double tlast=t0; unsigned long long bytes=0, pkts=0; int err; unsigned long long acc=0;
  while( (now_sec()-t0) < duration ){
    // Apply arithmetic op to payload region if requested
    if(pcpu_op){ apply_op(buf+sizeof(*eh), frame_sz-sizeof(*eh), pcpu_op, imm, &acc); }
    err = sendto(fd, buf, frame_sz, 0, (struct sockaddr*)&to, sizeof(to));
    if(err<0){ if(errno==ENOBUFS||errno==EAGAIN) continue; perror("sendto"); break; }
    bytes += (unsigned long long)err; pkts++;
    if((now_sec()-tlast) >= 1.0){
      double dt = now_sec()-t0; double mbps = (bytes/1e6)/dt;
      fprintf(stderr, "[TX] pkts=%llu bytes=%llu MB/s=%.1f\n", pkts, bytes, mbps);
      tlast = now_sec();
    }
  }
  double dt = now_sec()-t0; double mbps = dt>0 ? (bytes/1e6)/dt : 0.0;
  fprintf(stderr, "[TX DONE] pkts=%llu bytes=%llu time=%.3f s MB/s=%.1f acc=%llx\n", pkts, bytes, dt, mbps, acc);
  free(buf); close(fd); return 0;
}
