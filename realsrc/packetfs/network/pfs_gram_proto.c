#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <time.h>
#include <unistd.h>
#ifndef IOV_MAX
#define IOV_MAX 1024
#endif

#include "../memory/pfs_hugeblob.h"
#include "../gram/pfs_gram.h"

static const uint8_t PFS_MAGIC[4] = {'P','F','S','1'};

// Global runtime configuration (declared before use)
static int g_verbose=0; static double g_log_interval=1.0; static const char* g_huge_dir_default="/dev/hugepages"; static const char* g_blob_name_default="pfs_gram_blob"; static int g_no_prefault=0; static int g_no_fill=0; static int g_blob_keep=0; static const char* g_huge_dir_rt="/dev/hugepages"; static const char* g_blob_name_rt="pfs_gram_blob";

// FNV-1a 64-bit for integrity checks
static inline uint64_t fnv1a64_init(void){ return 1469598103934665603ULL; }
static inline uint64_t fnv1a64_update(uint64_t h, const void* data, size_t n){ const uint8_t* p=(const uint8_t*)data; for(size_t i=0;i<n;i++){ h ^= p[i]; h *= 1099511628211ULL; } return h; }
static inline uint64_t fnv1a64_digest(uint64_t h){ return h; }

enum { MSG_HELLO=1, MSG_GRAM_REQUEST=40, MSG_GRAM_DATA=41, MSG_GRAM_COMPLETE=42, MSG_ERROR=255 };

static volatile sig_atomic_t g_stop=0; static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec + ts.tv_nsec/1e9; }
static void die(const char*fmt,...){ va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);} 

static void frame_header(uint8_t hdr[12], uint32_t type, uint32_t len){ memcpy(hdr,PFS_MAGIC,4); uint32_t t=htonl(type), l=htonl(len); memcpy(hdr+4,&t,4); memcpy(hdr+8,&l,4); }
static int recv_exact(int fd, void* buf, size_t n){ uint8_t* p=(uint8_t*)buf; size_t got=0; while(got<n){ ssize_t r=recv(fd,p+got,n-got,0); if(r<0){ if(errno==EINTR) continue; return -1;} if(r==0) return -1; got+= (size_t)r;} return 0; }
static int recv_frame(int fd, uint32_t* type, uint8_t** data, uint32_t* len){ uint8_t hdr[12]; if(recv_exact(fd,hdr,12)<0) return -1; if(memcmp(hdr,PFS_MAGIC,4)!=0) return -1; uint32_t t,l; memcpy(&t,hdr+4,4); memcpy(&l,hdr+8,4); *type=ntohl(t); *len=ntohl(l); if(*len> (64*1024*1024)) return -1; if(*len>0){ *data=(uint8_t*)malloc(*len); if(!*data) return -1; if(recv_exact(fd,*data,*len)<0){ free(*data); return -1; } } else { *data=NULL; } return 0; }

static unsigned long long json_get_ull(const char* json, const char* key, unsigned long long defv){ const char* p=strstr(json,key); if(!p) return defv; p=strchr(p,':'); if(!p) return defv; p++; while(*p==' '||*p=='\t') p++; unsigned long long v=0; while(*p>='0' && *p<='9'){ v = v*10 + (unsigned long long)(*p - '0'); p++; } return v; }

static int tcp_connect(const char* host, int port){ int fd=socket(AF_INET,SOCK_STREAM,0); if(fd<0) die("socket: %s",strerror(errno)); int one=1; setsockopt(fd,IPPROTO_TCP,TCP_NODELAY,&one,sizeof(one)); int snd=16*1024*1024, rcv=16*1024*1024; setsockopt(fd,SOL_SOCKET,SO_SNDBUF,&snd,sizeof(snd)); setsockopt(fd,SOL_SOCKET,SO_RCVBUF,&rcv,sizeof(rcv)); struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_port=htons((uint16_t)port); if(inet_pton(AF_INET,host,&a.sin_addr)<=0) die("inet_pton %s",host); if(connect(fd,(struct sockaddr*)&a,sizeof(a))<0) die("connect: %s",strerror(errno)); return fd; }
static int tcp_listen(int port){ int fd=socket(AF_INET,SOCK_STREAM,0); if(fd<0) die("socket: %s",strerror(errno)); int one=1; setsockopt(fd,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one)); struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_addr.s_addr=htonl(INADDR_ANY); a.sin_port=htons((uint16_t)port); if(bind(fd,(struct sockaddr*)&a,sizeof(a))<0) die("bind: %s",strerror(errno)); if(listen(fd,64)<0) die("listen: %s",strerror(errno)); return fd; }

static int send_hello(int fd, const char* who){ char body[128]; int n=snprintf(body,sizeof(body),"{\"%s\":\"PacketFS-gram\"}", who); uint8_t hdr[12]; frame_header(hdr,MSG_HELLO,(uint32_t)n); struct iovec iov[2]={{hdr,12},{body,(size_t)n}}; size_t total=12+(size_t)n; size_t sent=0; while(sent<total){ ssize_t w=writev(fd,iov,2); if(w<0){ if(errno==EINTR) continue; return -1;} if((size_t)w==total) break; // partial: adjust
        size_t rem=(size_t)w; if(rem>=12){ iov[0].iov_len=0; iov[1].iov_base=(char*)iov[1].iov_base + (rem-12); iov[1].iov_len = (size_t)n - (rem-12);
        } else { iov[0].iov_base=(char*)iov[0].iov_base + rem; iov[0].iov_len = 12 - rem; }
        sent += (size_t)w;
    } return 0; }

static int send_frame_iov(int fd, uint32_t type, struct iovec* payload_iov, int payload_iovcnt, uint32_t payload_len){ uint8_t hdr[12]; frame_header(hdr,type,payload_len); struct iovec iov[1+payload_iovcnt]; iov[0].iov_base=hdr; iov[0].iov_len=12; for(int i=0;i<payload_iovcnt;i++){ iov[1+i]=payload_iov[i]; }
    size_t total = 12ULL + (size_t)payload_len; size_t sent=0; int iovcnt=1+payload_iovcnt; struct iovec* cur=iov; while(sent<total){ ssize_t w=writev(fd, cur, iovcnt); if(w<0){ if(errno==EINTR) continue; return -1;} sent += (size_t)w; // advance iov
        size_t adv=(size_t)w; for(int k=0;k<iovcnt && adv>0;k++){ if(adv>=cur[k].iov_len){ adv -= cur[k].iov_len; cur[k].iov_base=(char*)cur[k].iov_base + cur[k].iov_len; cur[k].iov_len=0; } else { cur[k].iov_base=(char*)cur[k].iov_base + adv; cur[k].iov_len -= adv; adv=0; } }
        while(iovcnt>0 && cur[0].iov_len==0){ cur++; iovcnt--; }
    }
    return 0; }

static int run_server(int port, size_t blob_size, uint64_t seed, uint32_t desc_per_gram, uint32_t gram_count, uint32_t max_len, uint32_t align){ int srv=tcp_listen(port); fprintf(stderr,"PFS gram server listening on 0.0.0.0:%d\n",port); int cfd=accept(srv,NULL,NULL); if(cfd<0) die("accept: %s",strerror(errno)); (void)send_hello(cfd,"server"); uint32_t t,l; uint8_t* body=NULL; if(recv_frame(cfd,&t,&body,&l)<0) die("recv hello"); if(t!=MSG_HELLO){ free(body); die("unexpected msg %u",t);} free(body);
    // expect GRAM_REQUEST
    if(recv_frame(cfd,&t,&body,&l)<0) die("recv req"); if(t!=MSG_GRAM_REQUEST){ free(body); die("unexpected %u",t);} // parse overrides from JSON
    const char* js=(const char*)body; size_t B = (size_t)json_get_ull(js,"\"blob_size\"", blob_size); uint64_t S = json_get_ull(js,"\"seed\"", seed); uint32_t D = (uint32_t)json_get_ull(js,"\"desc_per_gram\"", desc_per_gram); uint32_t G=(uint32_t)json_get_ull(js,"\"gram_count\"", gram_count); uint32_t ML=(uint32_t)json_get_ull(js,"\"max_len\"", max_len); uint32_t AL=(uint32_t)json_get_ull(js,"\"align\"", align); uint32_t PAY=(uint32_t)json_get_ull(js,"\"payload\"", 0ULL); uint64_t TOTAL=json_get_ull(js,"\"total_bytes\"", 0ULL); uint32_t GB=(uint32_t)json_get_ull(js,"\"gram_bytes\"", 1048576ULL); free(body);
    double tprep0=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] map start size=%zu huge_dir=%s name=%s\n", B, g_huge_dir_rt?g_huge_dir_rt:"(none)", g_blob_name_rt?g_blob_name_rt:"(none)");
    PfsHugeBlob blob; if(pfs_hugeblob_map(B, g_huge_dir_rt, g_blob_name_rt, &blob)!=0) die("map blob: %s", strerror(errno)); pfs_hugeblob_set_keep(&blob, g_blob_keep);
    double tprep1=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] map done method=%s dt=%.3fs\n", blob.hugetlbfs?"hugetlbfs":"anon(THP)", tprep1-tprep0);
    if(!g_no_prefault){ double tpf0=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] prefault start\n"); pfs_hugeblob_prefault(&blob,1); double tpf1=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] prefault done dt=%.3fs\n", tpf1-tpf0); }
    if(!g_no_fill){ double tf0=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] fill start seed=%llu\n", (unsigned long long)S); pfs_hugeblob_fill(&blob,S); double tf1=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] fill done dt=%.3fs\n", tf1-tf0); }
    PfsGramDesc* descs = (PfsGramDesc*)malloc(D * sizeof(PfsGramDesc)); if(!descs) die("desc alloc");
    uint8_t* header = (uint8_t*)malloc(sizeof(PfsGramHeader) + D*sizeof(PfsGramDesc)); if(!header) die("hdr alloc");
    double t0=now_sec(), tlast=t0; uint64_t gram_seq=0; unsigned long long effective=0ULL; uint64_t csum_tx = fnv1a64_init();
    if(PAY){
        uint64_t sent=0; while(sent < TOTAL && !g_stop){ uint32_t desc_use = D?D:1; if(desc_use > (uint32_t)(IOV_MAX - 2)) desc_use = (uint32_t)(IOV_MAX - 2); uint64_t remain = TOTAL - sent; uint32_t pay_this = (uint32_t)((remain < GB)? remain : GB);
            // even split across desc_use
            uint32_t base = pay_this / desc_use, extra = pay_this % desc_use; size_t ndesc=desc_use; uint64_t x=S+gram_seq*0x9e37ULL; for(uint32_t i=0;i<ndesc;i++){
                uint32_t len = base + (i==ndesc-1?extra:0); if(len==0){ ndesc=i; break; }
                // randomish offset aligned
                x ^= x>>12; x ^= x<<25; x ^= x>>27; x *= 2685821657736338717ULL; uint64_t off = x % (blob.size?blob.size:1); off &= ~((uint64_t)AL? ((uint64_t)AL-1ULL):0ULL); if(off + len > blob.size){ if(len > blob.size) len = (uint32_t)blob.size; off = blob.size - len; off &= ~((uint64_t)AL? ((uint64_t)AL-1ULL):0ULL); }
                descs[i].offset = off; descs[i].len = len; descs[i].flags=0;
            }
            PfsGramHeader* gh=(PfsGramHeader*)header; pfs_gram_header_write(gh, gram_seq++, (uint32_t)ndesc, pay_this, 1/*payload_present*/);
            memcpy(header+sizeof(PfsGramHeader), descs, ndesc*sizeof(PfsGramDesc)); uint32_t hdrlen=(uint32_t)(sizeof(PfsGramHeader)+ndesc*sizeof(PfsGramDesc));
            // Build payload iov list including gram header+descs, respect IOV_MAX
            int piovcnt = 1 + (int)ndesc; struct iovec* piov = (struct iovec*)malloc(sizeof(struct iovec)*piovcnt); if(!piov) die("iov alloc");
            piov[0].iov_base = header; piov[0].iov_len = hdrlen;
            for(size_t i=0;i<ndesc;i++){ piov[1+i].iov_base = (uint8_t*)blob.addr + descs[i].offset; piov[1+i].iov_len = descs[i].len; }
            if(send_frame_iov(cfd, MSG_GRAM_DATA, piov, piovcnt, hdrlen + pay_this)!=0) die("send gram payload");
            // checksum and accounting
            for(size_t i=0;i<ndesc;i++){ csum_tx = fnv1a64_update(csum_tx, (uint8_t*)blob.addr + descs[i].offset, descs[i].len); effective += descs[i].len; }
            sent += pay_this; free(piov);
            double tn=now_sec(); if(tn - tlast >= g_log_interval){ double mbps = (effective/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"SERVER payload TX: %.2f MB/s (%.1f MB)\n", mbps, effective/(1024.0*1024.0)); tlast=tn; }
        }
        char done[128]; snprintf(done,sizeof(done),"{\"status\":\"complete\",\"bytes\":%llu,\"checksum\":\"0x%016llx\"}",(unsigned long long)effective,(unsigned long long)fnv1a64_digest(csum_tx)); uint8_t hdr[12]; frame_header(hdr,MSG_GRAM_COMPLETE,(uint32_t)strlen(done)); struct iovec diov[2]={{hdr,12},{done,strlen(done)}}; (void)writev(cfd, diov, 2);
    } else {
        for(uint32_t g=0; g<G && !g_stop; g++){
            size_t ndesc = pfs_gram_gen_descs(S + g, blob.size, D, ML, AL, descs);
            PfsGramHeader* gh=(PfsGramHeader*)header; pfs_gram_header_write(gh, gram_seq++, (uint32_t)ndesc, 0ULL, 0);
            memcpy(header+sizeof(PfsGramHeader), descs, ndesc*sizeof(PfsGramDesc));
            uint32_t hdrlen = (uint32_t)(sizeof(PfsGramHeader) + ndesc*sizeof(PfsGramDesc));
            struct iovec iov[1]; iov[0].iov_base = header; iov[0].iov_len = hdrlen;
            if(send_frame_iov(cfd, MSG_GRAM_DATA, iov, 1, hdrlen)!=0) die("send gram");
            for(size_t i=0;i<ndesc;i++){ // compute checksum over described bytes for integrity
                csum_tx = fnv1a64_update(csum_tx, (uint8_t*)blob.addr + descs[i].offset, descs[i].len); effective += descs[i].len; }
            double tn=now_sec(); if(tn - tlast >= g_log_interval){ double mbps = (effective/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"SERVER effective TX: %.2f MB/s (%.1f MB)\n", mbps, effective/(1024.0*1024.0)); tlast = tn; }
        }
        char done[128]; snprintf(done,sizeof(done),"{\"status\":\"complete\",\"bytes\":%llu,\"checksum\":\"0x%016llx\"}",(unsigned long long)effective,(unsigned long long)fnv1a64_digest(csum_tx)); uint8_t hdr[12]; frame_header(hdr,MSG_GRAM_COMPLETE,(uint32_t)strlen(done)); struct iovec diov[2]={{hdr,12},{done,strlen(done)}}; (void)writev(cfd, diov, 2);
    }
    free(header); free(descs); pfs_hugeblob_unmap(&blob); close(cfd); close(srv); return 0; }

static uint64_t parse_hex_u64(const char* s){ if(!s) return 0; uint64_t v=0; if(s[0]=='0' && (s[1]=='x'||s[1]=='X')) s+=2; while(*s){ char c=*s++; uint8_t d; if(c>='0'&&c<='9') d=c-'0'; else if(c>='a'&&c<='f') d=10+(c-'a'); else if(c>='A'&&c<='F') d=10+(c-'A'); else break; v = (v<<4) | d; } return v; }

static int run_client(const char* host, int port, size_t blob_size, uint64_t seed, uint32_t desc_per_gram, uint32_t gram_count, uint32_t max_len, uint32_t align){ int fd=tcp_connect(host,port); (void)send_hello(fd,"client"); uint32_t t,l; uint8_t* body=NULL; if(recv_frame(fd,&t,&body,&l)<0) die("recv hello"); if(t!=MSG_HELLO){ free(body); die("unexpected %u",t);} free(body);
    // map blob locally
    double tprep0=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] client map start size=%zu huge_dir=%s name=%s\n", blob_size, g_huge_dir_rt?g_huge_dir_rt:"(none)", g_blob_name_rt?g_blob_name_rt:"(none)");
    PfsHugeBlob blob; if(pfs_hugeblob_map(blob_size, g_huge_dir_rt, g_blob_name_rt, &blob)!=0) die("map blob: %s", strerror(errno)); pfs_hugeblob_set_keep(&blob, g_blob_keep);
    double tprep1=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] client map done method=%s dt=%.3fs\n", blob.hugetlbfs?"hugetlbfs":"anon(THP)", tprep1-tprep0);
    if(!g_no_prefault){ double tpf0=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] client prefault start\n"); pfs_hugeblob_prefault(&blob,1); double tpf1=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] client prefault done dt=%.3fs\n", tpf1-tpf0); }
    if(!g_no_fill){ double tf0=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] client fill start seed=%llu\n", (unsigned long long)seed); pfs_hugeblob_fill(&blob,seed); double tf1=now_sec(); if(g_verbose) fprintf(stderr,"[GRAM] client fill done dt=%.3fs\n", tf1-tf0); }
    // request parameters
    const char* env_pay = getenv("PFS_PAYLOAD"); // optional override
    int payload = env_pay ? atoi(env_pay) : 0; const char* env_total = getenv("PFS_TOTAL_BYTES"); uint64_t total = env_total? strtoull(env_total,NULL,10): 0ULL; const char* env_gb = getenv("PFS_GRAM_BYTES"); uint32_t gram_bytes = env_gb? (uint32_t)strtoul(env_gb,NULL,10): 1048576U;
    // send request JSON
    char req[384]; int rn=snprintf(req,sizeof(req),"{\"blob_size\": %zu, \"seed\": %llu, \"desc_per_gram\": %u, \"gram_count\": %u, \"max_len\": %u, \"align\": %u, \"payload\": %d, \"total_bytes\": %llu, \"gram_bytes\": %u}", blob.size, (unsigned long long)seed, desc_per_gram, gram_count, max_len, align, payload, (unsigned long long)total, gram_bytes); uint8_t hdr[12]; frame_header(hdr,MSG_GRAM_REQUEST,(uint32_t)rn); struct iovec riov[2]={{hdr,12},{req,(size_t)rn}}; (void)writev(fd,riov,2);
    double t0=now_sec(), tlast=t0; unsigned long long effective=0ULL; uint64_t csum_rx = fnv1a64_init(); uint32_t grams=0;
    for(;;){ if(recv_frame(fd,&t,&body,&l)<0) die("recv gram"); if(t==MSG_GRAM_DATA){ if(l < sizeof(PfsGramHeader)){ free(body); die("short gram"); } PfsGramHeader* gh=(PfsGramHeader*)body; if(gh->magic != PFS_GRAM_MAGIC){ free(body); die("bad magic"); } size_t desc_bytes = gh->header_len - sizeof(PfsGramHeader); if(sizeof(PfsGramHeader)+desc_bytes > (size_t)l){ free(body); die("bad header_len"); } size_t ndesc = desc_bytes / sizeof(PfsGramDesc); PfsGramDesc* descs = (PfsGramDesc*)(body + sizeof(PfsGramHeader)); if(gh->flags & 1){ // payload present
                size_t hdrlen = gh->header_len; size_t paylen = (size_t)gh->payload_len; if(hdrlen + paylen != (size_t)l){ free(body); die("bad gram payload len"); } csum_rx = fnv1a64_update(csum_rx, body + hdrlen, paylen); effective += paylen; }
            else { // offset-only integrity by reading blob
                for(size_t i=0;i<ndesc;i++){ csum_rx = fnv1a64_update(csum_rx, (uint8_t*)blob.addr + descs[i].offset, descs[i].len); effective += descs[i].len; }
            }
            free(body); grams++;
            double tn=now_sec(); if(tn - tlast >= g_log_interval){ double mbps = (effective/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"CLIENT effective RX: %.2f MB/s (%.1f MB)\n", mbps, effective/(1024.0*1024.0)); tlast = tn; }
        } else if(t==MSG_GRAM_COMPLETE){ // compare checksum
            uint64_t remote=0ULL; if(l>0){ const char* s=(const char*)body; const char* p=strstr(s,"\"checksum\":\""); if(p){ p+=12; const char* q=strchr(p,'\"'); char buf[40]={0}; size_t n=(size_t)(q? (size_t)(q-p): (size_t)0); if(n>0 && n<sizeof(buf)){ memcpy(buf,p,n); buf[n]=0; remote = parse_hex_u64(buf); } } }
            uint64_t local = fnv1a64_digest(csum_rx); fprintf(stderr,"complete: %.*s\n", (int)l, (char*)body); if(remote==local){ fprintf(stderr,"checksum OK: 0x%016llx bytes=%llu\n", (unsigned long long)local, (unsigned long long)effective); } else { fprintf(stderr,"checksum MISMATCH: local=0x%016llx remote=0x%016llx bytes=%llu\n", (unsigned long long)local, (unsigned long long)remote, (unsigned long long)effective); }
            free(body); break; } else { free(body); die("unexpected msg %u", t); }
        if(grams >= gram_count) { /* wait for complete */ }
    }
    pfs_hugeblob_unmap(&blob); close(fd); return 0; }


int main(int argc, char** argv){ signal(SIGINT,on_sigint); const char* mode=NULL; const char* host="127.0.0.1"; int port=8433; size_t blob_size = 1ULL<<30; // 1 GiB default
    uint64_t seed=0x12345678ULL; uint32_t desc_per_gram=16; uint32_t gram_count=4096; uint32_t max_len=64*1024; uint32_t align=64; const char* huge_dir=g_huge_dir_default; const char* blob_name=g_blob_name_default;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--mode") && i+1<argc) mode=argv[++i];
        else if(!strcmp(argv[i],"--host") && i+1<argc) host=argv[++i];
        else if(!strcmp(argv[i],"--port") && i+1<argc) port=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--blob-size") && i+1<argc) blob_size=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--seed") && i+1<argc) seed=strtoull(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--desc-per-gram") && i+1<argc) desc_per_gram=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--gram-count") && i+1<argc) gram_count=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--max-len") && i+1<argc) max_len=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--align") && i+1<argc) align=(uint32_t)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--huge-dir") && i+1<argc) huge_dir=argv[++i];
        else if(!strcmp(argv[i],"--blob-name") && i+1<argc) blob_name=argv[++i];
        else if(!strcmp(argv[i],"--no-prefault")) g_no_prefault=1;
        else if(!strcmp(argv[i],"--no-fill")) g_no_fill=1;
        else if(!strcmp(argv[i],"--blob-keep")) g_blob_keep=1;
        else if(!strcmp(argv[i],"--verbose")) g_verbose=1;
        else if(!strcmp(argv[i],"--log-interval") && i+1<argc) g_log_interval=strtod(argv[++i],NULL);
        else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")){
            printf("Usage: %s --mode server|client [--host H] [--port P]\n", argv[0]);
            printf("       common: --blob-size BYTES --seed S --desc-per-gram N --gram-count G --max-len L --align A\n");
            printf("               --huge-dir DIR --blob-name NAME [--no-prefault] [--no-fill] [--blob-keep] [--verbose] [--log-interval S]\n");
            return 0;
        }
    }
    if(!mode) die("--mode required");
    if(g_verbose) fprintf(stderr,"[GRAM] cfg mode=%s host=%s port=%d blob_size=%zu seed=%llu dpg=%u grams=%u max_len=%u align=%u huge_dir=%s name=%s no_prefault=%d no_fill=%d keep=%d\n",
        mode?mode:"?", host, port, blob_size, (unsigned long long)seed, desc_per_gram, gram_count, max_len, align, huge_dir?huge_dir:"(none)", blob_name?blob_name:"(none)", g_no_prefault, g_no_fill, g_blob_keep);
    g_huge_dir_rt = huge_dir; g_blob_name_rt = blob_name;
    if(!strcmp(mode,"server")) return run_server(port, blob_size, seed, desc_per_gram, gram_count, max_len, align);
    else if(!strcmp(mode,"client")) return run_client(host, port, blob_size, seed, desc_per_gram, gram_count, max_len, align);
    else die("unknown mode");
}

