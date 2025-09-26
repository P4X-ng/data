// dev/tools/syn_scan.c — Minimal high-speed SYN scanner (inspired by masscan)
// REQUIREMENTS: root (raw socket), Linux IPv4
// Note: Use only on networks you own or have permission to scan.
// Build: gcc -O3 -march=native -DNDEBUG -pthread -o dev/tools/syn_scan dev/tools/syn_scan.c
// Example:
//   sudo dev/tools/syn_scan --cidr 10.0.0.0/24 --ports 80,443,22-25 \
//     --src-ip 10.0.0.10 --src-port 40000 --pps 200000

#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/ip.h>
#include <netinet/tcp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

static inline uint64_t now_ns(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return (uint64_t)ts.tv_sec*1000000000ull + ts.tv_nsec; }

static uint16_t csum16(const void *buf, size_t len){
  uint32_t sum = 0; const uint16_t* p = (const uint16_t*)buf;
  while (len > 1) { sum += *p++; len -= 2; }
  if (len) sum += *(const uint8_t*)p;
  while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
  return (uint16_t)(~sum);
}

static uint16_t tcp_checksum(const struct iphdr* iph, const struct tcphdr* tcph, size_t tcp_len){
  struct pseudo {
    uint32_t saddr;
    uint32_t daddr;
    uint8_t  zero;
    uint8_t  proto;
    uint16_t len;
  } __attribute__((packed)) ph;
  ph.saddr = iph->saddr; ph.daddr = iph->daddr; ph.zero=0; ph.proto=IPPROTO_TCP; ph.len=htons((uint16_t)tcp_len);
  uint32_t sum = 0;
  const uint16_t* p;
  // pseudo header
  p = (const uint16_t*)&ph; for(size_t i=0;i<sizeof(ph)/2;i++) sum += *p++;
  // tcp header (no options, no data)
  p = (const uint16_t*)tcph; for(size_t i=0;i<tcp_len/2;i++) sum += *p++;
  while (sum >> 16) sum = (sum & 0xFFFF) + (sum >> 16);
  return (uint16_t)(~sum);
}

static int parse_cidr(const char* s, uint32_t* out_base, uint32_t* out_count){
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

#define MAX_PORTS 65536
static uint16_t PORTS[MAX_PORTS];
static size_t   NPORTS = 0;

static int parse_ports(const char* s){
  // format: "80,443,22-25"
  char* tmp = strdup(s); if(!tmp) return -1; char* save=tmp;
  char* tok;
  while((tok = strsep(&tmp, ","))){
    if(!*tok) continue;
    char* dash = strchr(tok,'-');
    if(dash){ *dash='\0'; int a=atoi(tok), b=atoi(dash+1); if(a<1||b<1||a>65535||b>65535||a>b){ free(save); return -1; }
      for(int p=a;p<=b;p++){ if(NPORTS<MAX_PORTS) PORTS[NPORTS++]=(uint16_t)p; }
    } else {
      int p = atoi(tok); if(p<1||p>65535){ free(save); return -1; }
      if(NPORTS<MAX_PORTS) PORTS[NPORTS++]=(uint16_t)p;
    }
  }
  free(save);
  return (NPORTS>0)?0:-1;
}

static void usage(const char* argv0){
  fprintf(stderr,
    "Usage: sudo %s --cidr A.B.C.D/NN --ports LIST --src-ip A.B.C.D [--src-port N] [--pps N] [--ttl N]\n",
    argv0);
}

int main(int argc, char** argv){
  const char* cidr=NULL; const char* ports=NULL; const char* src_ip_s=NULL;
  uint32_t src_ip=0; uint16_t src_port=40000; uint32_t pps=100000; int ttl=64;

  for(int i=1;i<argc;i++){
    if(!strcmp(argv[i],"--cidr")&&i+1<argc) cidr=argv[++i];
    else if(!strcmp(argv[i],"--ports")&&i+1<argc) ports=argv[++i];
    else if(!strcmp(argv[i],"--src-ip")&&i+1<argc) src_ip_s=argv[++i];
    else if(!strcmp(argv[i],"--src-port")&&i+1<argc) src_port=(uint16_t)atoi(argv[++i]);
    else if(!strcmp(argv[i],"--pps")&&i+1<argc) pps=(uint32_t)strtoul(argv[++i],NULL,10);
    else if(!strcmp(argv[i],"--ttl")&&i+1<argc) ttl=atoi(argv[++i]);
    else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){ usage(argv[0]); return 0; }
  }
  if(!cidr || !ports || !src_ip_s){ usage(argv[0]); return 2; }
  struct in_addr sin; if(inet_aton(src_ip_s,&sin)==0){ fprintf(stderr,"bad --src-ip\n"); return 2; }
  src_ip = sin.s_addr; // network order
  if(parse_ports(ports)!=0){ fprintf(stderr,"bad --ports\n"); return 2; }

  uint32_t base=0,count=0; if(parse_cidr(cidr,&base,&count)!=0){ fprintf(stderr,"bad --cidr\n"); return 2; }

  int s = socket(AF_INET, SOCK_RAW, IPPROTO_TCP);
  if(s<0){ perror("socket raw TCP"); return 1; }
  int on=1; if(setsockopt(s, IPPROTO_IP, IP_HDRINCL, &on, sizeof(on))<0){ perror("setsockopt IP_HDRINCL"); return 1; }

  // pacing
  double interval_ns = (pps>0)? (1e9 / (double)pps) : 0.0;
  uint64_t next_ns = now_ns();

  uint64_t sent=0; uint64_t t0=now_ns(); uint64_t next_print=t0+1000000000ull; uint16_t id=1;

  // Pre-build header templates
  unsigned char packet[60]; // enough for IP+TCP no options
  memset(packet,0,sizeof(packet));
  struct iphdr* iph = (struct iphdr*)packet;
  struct tcphdr* tcph = (struct tcphdr*)(packet + sizeof(struct iphdr));

  iph->version = 4; iph->ihl = 5; iph->tos = 0;
  iph->tot_len = htons(sizeof(struct iphdr) + sizeof(struct tcphdr));
  iph->id = htons(id);
  iph->frag_off = 0;
  iph->ttl = (uint8_t)ttl;
  iph->protocol = IPPROTO_TCP;
  iph->saddr = src_ip; // already network order

  tcph->doff = 5; // no options
  tcph->syn = 1;
  tcph->window = htons(1024);
  tcph->urg_ptr = 0;

  struct sockaddr_in dst = {0}; dst.sin_family = AF_INET;

  for(uint32_t i=0;i<count;i++){
    uint32_t ip_h = base + i; // host order
    uint32_t ip_n = htonl(ip_h);
    dst.sin_addr.s_addr = ip_n;
    for(size_t pi=0; pi<NPORTS; pi++){
      uint16_t dport = PORTS[pi];
      // Fill per-packet fields
      iph->id = htons(id++);
      iph->daddr = ip_n;
      iph->check = 0; iph->check = csum16(iph, sizeof(*iph));

      tcph->source = htons(src_port);
      tcph->dest = htons(dport);
      tcph->seq = htonl((uint32_t)((ip_h*2654435761u) ^ dport));
      tcph->ack_seq = 0;
      tcph->res1 = 0; tcph->cwr=0; tcph->ece=0; tcph->urg=0; tcph->ack=0; tcph->psh=0; tcph->rst=0; tcph->fin=0; tcph->syn=1;
      tcph->check = 0; tcph->check = tcp_checksum(iph, tcph, sizeof(*tcph));

      ssize_t n = sendto(s, packet, sizeof(struct iphdr)+sizeof(struct tcphdr), 0, (struct sockaddr*)&dst, sizeof(dst));
      if(n<0){ if(errno==EPERM||errno==EACCES) { perror("sendto"); fprintf(stderr,"Need root for raw socket.\n"); return 1; } }
      sent++;

      // pacing
      if(interval_ns>0){
        next_ns += (uint64_t)interval_ns;
        uint64_t now = now_ns();
        if(next_ns > now){
          struct timespec ts; uint64_t d=next_ns-now; ts.tv_sec=d/1000000000ull; ts.tv_nsec=d%1000000000ull; nanosleep(&ts,NULL);
        } else {
          next_ns = now; // catch up
        }
      }

      if(now_ns()>=next_print){
        double secs = (now_ns()-t0)/1e9; fprintf(stdout,"[syn] sent=%llu avg_pps=%.0f\n",
          (unsigned long long)sent, sent/secs);
        next_print += 1000000000ull;
      }
    }
  }

  fprintf(stdout,"[syn DONE] sent=%llu\n", (unsigned long long)sent);
  close(s); return 0;
}
