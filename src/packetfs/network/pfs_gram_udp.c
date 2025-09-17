#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>

#include "../memory/pfs_hugeblob.h"
#include "../gram/pfs_gram.h"

static inline double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec + ts.tv_nsec/1e9; }
static void die(const char* msg){ perror(msg); exit(1); }

static inline uint64_t fnv1a64_init(void){ return 1469598103934665603ULL; }
static inline uint64_t fnv1a64_update(uint64_t h, const void* data, size_t n){ const uint8_t* p=(const uint8_t*)data; for(size_t i=0;i<n;i++){ h ^= p[i]; h *= 1099511628211ULL; } return h; }

static unsigned long long json_get_ull(const char* json, const char* key, unsigned long long defv){ const char* p=strstr(json,key); if(!p) return defv; p=strchr(p,':'); if(!p) return defv; p++; while(*p==' '||*p=='\t') p++; unsigned long long v=0; while(*p>='0' && *p<='9'){ v = v*10 + (unsigned long long)(*p - '0'); p++; } return v; }

static int udp_bind(int port){ int fd=socket(AF_INET,SOCK_DGRAM,0); if(fd<0) die("socket"); int one=1; setsockopt(fd,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one)); int snd=16*1024*1024, rcv=16*1024*1024; setsockopt(fd,SOL_SOCKET,SO_SNDBUF,&snd,sizeof(snd)); setsockopt(fd,SOL_SOCKET,SO_RCVBUF,&rcv,sizeof(rcv)); struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_addr.s_addr=htonl(INADDR_ANY); a.sin_port=htons((uint16_t)port); if(bind(fd,(struct sockaddr*)&a,sizeof(a))<0) die("bind"); return fd; }
static int udp_connect(const char* host,int port){ int fd=socket(AF_INET,SOCK_DGRAM,0); if(fd<0) die("socket"); int snd=16*1024*1024, rcv=16*1024*1024; setsockopt(fd,SOL_SOCKET,SO_SNDBUF,&snd,sizeof(snd)); setsockopt(fd,SOL_SOCKET,SO_RCVBUF,&rcv,sizeof(rcv)); struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_port=htons((uint16_t)port); if(inet_pton(AF_INET,host,&a.sin_addr)<=0) die("inet_pton"); if(connect(fd,(struct sockaddr*)&a,sizeof(a))<0) die("connect"); return fd; }

static void server(int port, size_t blob_size, uint64_t seed, uint32_t desc_per_gram, uint64_t total_bytes, uint32_t gram_bytes, uint32_t align){ int fd=udp_bind(port); fprintf(stderr,"UDP gram server on 0.0.0.0:%d\n",port); struct sockaddr_in peer; socklen_t pl=sizeof(peer); char req[512]; ssize_t r = recvfrom(fd, req, sizeof(req)-1, 0, (struct sockaddr*)&peer, &pl); if(r<=0) die("recvfrom"); req[r]=0;
    size_t B=(size_t)json_get_ull(req,"\"blob_size\"", blob_size); uint64_t S=json_get_ull(req,"\"seed\"", seed); uint32_t D=(uint32_t)json_get_ull(req,"\"desc_per_gram\"", desc_per_gram); uint64_t T=json_get_ull(req,"\"total_bytes\"", total_bytes); uint32_t GB=(uint32_t)json_get_ull(req,"\"gram_bytes\"", gram_bytes); if(T==0) T=1ULL<<30; if(GB>64000) GB=64000; if(D==0) D=16; if(align==0) align=64;
    PfsHugeBlob blob; if(pfs_hugeblob_map(B, "/dev/hugepages", "pfs_udp_blob", &blob)!=0) die("map blob"); pfs_hugeblob_prefault(&blob,1); pfs_hugeblob_fill(&blob,S);
    uint8_t* hdrbuf = (uint8_t*)malloc(sizeof(PfsGramHeader)+D*sizeof(PfsGramDesc)); if(!hdrbuf) die("hdrbuf"); PfsGramDesc* descs=(PfsGramDesc*)(hdrbuf+sizeof(PfsGramHeader)); uint64_t sent=0; uint64_t seq=0; uint64_t csum=fnv1a64_init(); double t0=now_sec(), tlast=t0; while(sent<T){ uint32_t pay = (uint32_t)((T - sent < GB)? (T - sent) : GB); uint32_t base = pay / D, extra = pay % D; size_t ndesc=D; uint64_t x=S+seq*0x9e37ULL; for(uint32_t i=0;i<ndesc;i++){ uint32_t len = base + (i==ndesc-1?extra:0); if(len==0){ ndesc=i; break; } x ^= x>>12; x ^= x<<25; x ^= x>>27; x *= 2685821657736338717ULL; uint64_t off = x % (blob.size?blob.size:1); off &= ~((uint64_t)align - 1ULL); if(off+len>blob.size){ if(len>blob.size) len=(uint32_t)blob.size; off=blob.size-len; off &= ~((uint64_t)align -1ULL);} descs[i].offset=off; descs[i].len=len; descs[i].flags=0; }
        PfsGramHeader* gh=(PfsGramHeader*)hdrbuf; pfs_gram_header_write(gh, seq++, (uint32_t)ndesc, pay, 1);
        size_t hdrlen = sizeof(PfsGramHeader) + ndesc*sizeof(PfsGramDesc);
        struct iovec iov[1+ndesc]; iov[0].iov_base=hdrbuf; iov[0].iov_len=hdrlen; for(size_t i=0;i<ndesc;i++){ iov[1+i].iov_base = (uint8_t*)blob.addr + descs[i].offset; iov[1+i].iov_len = descs[i].len; }
        struct msghdr msg; memset(&msg,0,sizeof(msg)); msg.msg_name=&peer; msg.msg_namelen=sizeof(peer); msg.msg_iov=iov; msg.msg_iovlen=1+ndesc; if(sendmsg(fd,&msg,0)<0) die("sendmsg");
        for(size_t i=0;i<ndesc;i++){ csum = fnv1a64_update(csum, (uint8_t*)blob.addr + descs[i].offset, descs[i].len); }
        sent += pay; double tn=now_sec(); if(tn - tlast >= 1.0){ double mbps=(sent/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"SERVER UDP payload TX: %.2f MB/s (%.1f MB)\n", mbps, sent/(1024.0*1024.0)); tlast=tn; }
    }
    // final checksum datagram (JSON only)
    char done[128]; int dn=snprintf(done,sizeof(done),"{\"status\":\"complete\",\"bytes\":%llu,\"checksum\":\"0x%016llx\"}",(unsigned long long)sent,(unsigned long long)csum); if(sendto(fd,done,dn,0,(struct sockaddr*)&peer,sizeof(peer))<0) die("sendto");
    free(hdrbuf); pfs_hugeblob_unmap(&blob); close(fd);
}

static void client(const char* host,int port,size_t blob_size,uint64_t seed,uint32_t desc_per_gram,uint64_t total_bytes,uint32_t gram_bytes,uint32_t align){ int fd=udp_connect(host,port); char req[256]; int rn=snprintf(req,sizeof(req),"{\"blob_size\": %zu, \"seed\": %llu, \"desc_per_gram\": %u, \"total_bytes\": %llu, \"gram_bytes\": %u}", blob_size, (unsigned long long)seed, desc_per_gram, (unsigned long long)total_bytes, gram_bytes); if(send(fd,req,rn,0)<0) die("send req");
    PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, "/dev/hugepages", "pfs_udp_blob", &blob)!=0) die("map blob"); pfs_hugeblob_prefault(&blob,1); pfs_hugeblob_fill(&blob,seed);
    uint8_t* buf=(uint8_t*)malloc(70000); if(!buf) die("malloc"); uint64_t rx=0; uint64_t csum_payload=fnv1a64_init(); uint64_t csum_blob=fnv1a64_init(); double t0=now_sec(), tlast=t0; for(;;){ ssize_t r = recv(fd, buf, 70000, 0); if(r<0) die("recv"); if(r==0) continue; if(buf[0]=='{'){ // complete JSON
            buf[r]=0; const char* s=(const char*)buf; const char* p=strstr(s,"\"checksum\":\""); uint64_t remote=0ULL; if(p){ p+=12; char hex[40]={0}; const char* q=strchr(p,'\"'); size_t n=(size_t)(q?(q-p):0); if(n>0 && n<sizeof(hex)){ memcpy(hex,p,n); hex[n]=0; // parse
                        const char* h=hex; if(h[0]=='0' && (h[1]=='x'||h[1]=='X')) h+=2; while(*h){ char c=*h++; uint8_t d; if(c>='0'&&c<='9') d=c-'0'; else if(c>='a'&&c<='f') d=10+(c-'a'); else if(c>='A'&&c<='F') d=10+(c-'A'); else break; remote = (remote<<4)|d; } } }
            fprintf(stderr,"complete: %s\n", (char*)buf); fprintf(stderr,"checksum payload=0x%016llx blob=0x%016llx %s bytes=%llu\n", (unsigned long long)csum_payload,(unsigned long long)csum_blob,(csum_payload==remote?"OK":"(local vs remote unknown)"),(unsigned long long)rx); break; }
        if((size_t)r < sizeof(PfsGramHeader)) continue; PfsGramHeader* gh=(PfsGramHeader*)buf; size_t header_len = gh->header_len; if((size_t)r < header_len) continue; size_t desc_bytes = header_len - sizeof(PfsGramHeader); size_t ndesc = desc_bytes / sizeof(PfsGramDesc); PfsGramDesc* descs=(PfsGramDesc*)(buf+sizeof(PfsGramHeader)); size_t paylen = (size_t)gh->payload_len; if(header_len + paylen != (size_t)r) continue; // malformed
        csum_payload = fnv1a64_update(csum_payload, buf + header_len, paylen);
        for(size_t i=0;i<ndesc;i++){ csum_blob = fnv1a64_update(csum_blob, (uint8_t*)blob.addr + descs[i].offset, descs[i].len); }
        rx += paylen; double tn=now_sec(); if(tn - tlast >= 1.0){ double mbps=(rx/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"CLIENT UDP payload RX: %.2f MB/s (%.1f MB)\n", mbps, rx/(1024.0*1024.0)); tlast=tn; }
    }
    free(buf); pfs_hugeblob_unmap(&blob); close(fd);
}

int main(int argc,char**argv){ const char* mode=NULL; const char* host="127.0.0.1"; int port=8533; size_t blob_size=1ULL<<30; uint64_t seed=0x12345678ULL; uint32_t desc_per_gram=16; uint64_t total_bytes=1ULL<<30; uint32_t gram_bytes=60000; uint32_t align=64; for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--mode")&&i+1<argc) mode=argv[++i]; else if(!strcmp(argv[i],"--host")&&i+1<argc) host=argv[++i]; else if(!strcmp(argv[i],"--port")&&i+1<argc) port=atoi(argv[++i]); else if(!strcmp(argv[i],"--blob-size")&&i+1<argc) blob_size=strtoull(argv[++i],NULL,10); else if(!strcmp(argv[i],"--seed")&&i+1<argc) seed=strtoull(argv[++i],NULL,10); else if(!strcmp(argv[i],"--desc-per-gram")&&i+1<argc) desc_per_gram=(uint32_t)strtoul(argv[++i],NULL,10); else if(!strcmp(argv[i],"--total-bytes")&&i+1<argc) total_bytes=strtoull(argv[++i],NULL,10); else if(!strcmp(argv[i],"--gram-bytes")&&i+1<argc) gram_bytes=(uint32_t)strtoul(argv[++i],NULL,10); else if(!strcmp(argv[i],"--align")&&i+1<argc) align=(uint32_t)strtoul(argv[++i],NULL,10); else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){ printf("Usage: %s --mode server|client [--host H] [--port P] [--blob-size N] [--desc-per-gram N] [--total-bytes N] [--gram-bytes N]\n", argv[0]); return 0; } }
    if(!mode){ fprintf(stderr,"--mode required\n"); return 1; }
    if(!strcmp(mode,"server")) server(port, blob_size, seed, desc_per_gram, total_bytes, gram_bytes, align);
    else if(!strcmp(mode,"client")) client(host, port, blob_size, seed, desc_per_gram, total_bytes, gram_bytes, align);
    else { fprintf(stderr,"unknown mode\n"); return 1; }
    return 0;
}

