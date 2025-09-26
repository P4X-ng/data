// PacketFS native async protocol prototype with ring-buffered TX
// Implements minimal PacketFS framing (PFS1 | msg_type | len) and two roles:
//   --mode server: accepts TCP, handles HELLO and BLUEPRINT_REQUEST, replies HELLO/FILE_COMPLETE
//   --mode client: sends HELLO, then BLUEPRINT_REQUEST with a blueprint JSON file, waits for FILE_COMPLETE
// Networking: single-threaded; TX uses a page-aligned ring buffer and non-blocking socket with EAGAIN pacing.
// Build: cc -O3 -march=native -DNDEBUG -pthread -o dev/wip/native/pfs_proto_async realsrc/packetfs/network/pfs_proto_async.c

#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <signal.h>
#include <stdarg.h>
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

static const uint8_t PFS_MAGIC[4] = {'P','F','S','1'};

enum { MSG_HELLO=1, MSG_SYNC_REQUEST=2, MSG_SYNC_DATA=3, MSG_FILE_REQUEST=4, MSG_FILE_DATA=5, MSG_FILE_COMPLETE=6, MSG_BLUEPRINT_REQUEST=7, MSG_FILE_STREAM_START=8, MSG_ERROR=255 };

static int run_server_stream(int cfd, const char* json);
static int run_server_stream_raw(int cfd, unsigned long long size);
static int stream_recv_raw(int fd, unsigned long long size);

static volatile sig_atomic_t g_stop=0; static void on_sigint(int sig){ (void)sig; g_stop=1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec + ts.tv_nsec/1e9; }
static void die(const char*fmt,...){ va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);} 
static void* xaligned_alloc(size_t a,size_t s){ void* p=NULL; if(posix_memalign(&p,a,s)!=0) return NULL; memset(p,0,s); return p; }
static int set_nonblock(int fd){ int fl=fcntl(fd,F_GETFL,0); return fcntl(fd,F_SETFL,fl|O_NONBLOCK); }

// Simple ring buffer for TX bytes
typedef struct { uint8_t* buf; size_t cap; size_t head; size_t tail; } tx_ring_t;
static tx_ring_t ring_new(size_t cap){ tx_ring_t r; r.buf=(uint8_t*)xaligned_alloc(4096,cap); if(!r.buf) die("ring alloc"); r.cap=cap; r.head=r.tail=0; return r; }
static size_t ring_free(const tx_ring_t* r){ if(r->head>=r->tail) return r->cap - (r->head - r->tail) - 1; else return (r->tail - r->head) - 1; }
static size_t ring_used(const tx_ring_t* r){ if(r->head>=r->tail) return r->head - r->tail; else return r->cap - (r->tail - r->head); }
static size_t ring_write(tx_ring_t* r, const void* data, size_t n){ size_t f=ring_free(r); if(n>f) n=f; size_t h=r->head; size_t first = (h + n <= r->cap)? n : (r->cap - h); memcpy(r->buf + h, data, first); if(n>first){ memcpy(r->buf, (const uint8_t*)data + first, n-first);} r->head = (h + n) % r->cap; return n; }
static size_t ring_peek(const tx_ring_t* r, struct iovec vec[2]){ size_t used=ring_used(r); if(used==0){ vec[0].iov_base=NULL; vec[0].iov_len=0; vec[1].iov_base=NULL; vec[1].iov_len=0; return 0; } size_t t=r->tail; size_t first = (t + used <= r->cap)? used : (r->cap - t); vec[0].iov_base = (void*)(r->buf + t); vec[0].iov_len = first; vec[1].iov_base = NULL; vec[1].iov_len = 0; if(used>first){ vec[1].iov_base = (void*)r->buf; vec[1].iov_len = used - first; } return used; }
static void ring_pop(tx_ring_t* r, size_t n){ size_t u=ring_used(r); if(n>u) n=u; r->tail = (r->tail + n) % r->cap; }

// Framing helpers
static void frame_header(uint8_t hdr[12], uint32_t type, uint32_t len){ memcpy(hdr,PFS_MAGIC,4); uint32_t t=htonl(type), l=htonl(len); memcpy(hdr+4,&t,4); memcpy(hdr+8,&l,4); }

static int pump_tx_nonblock(int fd, tx_ring_t* tx){ struct iovec vec[2]; size_t used = ring_peek(tx, vec); if(used==0) return 0; ssize_t w = writev(fd, vec, (vec[1].iov_len>0)?2:1); if(w<0){ if(errno==EAGAIN||errno==EWOULDBLOCK) return 0; return -1; } if(w>0) ring_pop(tx,(size_t)w); return (int)w; }

static int send_frame(int fd, tx_ring_t* tx, uint32_t type, const uint8_t* data, uint32_t len){ uint8_t hdr[12]; frame_header(hdr,type,len); size_t need = 12 + len; if(ring_free(tx) < need){ // pump until space
        for(int i=0;i<100 && ring_free(tx)<need;i++){ int r=pump_tx_nonblock(fd,tx); if(r<0) return -1; if(r==0){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL);} }
        if(ring_free(tx) < need) return -1;
    }
    ring_write(tx,hdr,12); if(len>0) ring_write(tx,data,len); return 0; }

static int recv_exact(int fd, void* buf, size_t n){ uint8_t* p=(uint8_t*)buf; size_t got=0; while(got<n){ ssize_t r=recv(fd,p+got,n-got,0); if(r<0){ if(errno==EINTR) continue; return -1;} if(r==0) return -1; got+= (size_t)r;} return 0; }

static int recv_frame(int fd, uint32_t* type, uint8_t** data, uint32_t* len){ uint8_t hdr[12]; if(recv_exact(fd,hdr,12)<0) return -1; if(memcmp(hdr,PFS_MAGIC,4)!=0) return -1; uint32_t t,l; memcpy(&t,hdr+4,4); memcpy(&l,hdr+8,4); *type=ntohl(t); *len=ntohl(l); if(*len> (64*1024*1024)) return -1; // guard 64MB
    if(*len>0){ *data=(uint8_t*)malloc(*len); if(!*data) return -1; if(recv_exact(fd,*data,*len)<0){ free(*data); return -1; } } else { *data=NULL; } return 0; }

// Server: handle one client connection
static int server_handle(int cfd){ /* blocking socket */ tx_ring_t tx = ring_new(1<<20); // 1MB TX ring
    double t_last = now_sec();
    for(;;){ // pump tx periodically
        (void)pump_tx_nonblock(cfd,&tx);
        // try to read a frame (blocking header)
        uint32_t type,len; uint8_t* body=NULL; int r=recv_frame(cfd,&type,&body,&len); if(r<0){ break; }
        if(type==MSG_HELLO){ const char* resp="{\"server\":\"PacketFS-Native\",\"features\":[\"file-transfer\",\"blueprint\"]}"; send_frame(cfd,&tx,MSG_HELLO,(const uint8_t*)resp,(uint32_t)strlen(resp)); (void)pump_tx_nonblock(cfd,&tx); }
        else if(type==MSG_BLUEPRINT_REQUEST){ // acknowledge blueprint, do not transfer content
            const char* ack="{\"status\":\"blueprint-accepted\"}"; send_frame(cfd,&tx,MSG_FILE_COMPLETE,(const uint8_t*)ack,(uint32_t)strlen(ack)); (void)pump_tx_nonblock(cfd,&tx); free(body); break; }
        else if(type==MSG_FILE_REQUEST){ if(body){ run_server_stream(cfd,(const char*)body); } free(body); break; }
        else { const char* err="{\"error\":\"unsupported\"}"; send_frame(cfd,&tx,MSG_ERROR,(const uint8_t*)err,(uint32_t)strlen(err)); }
        free(body);
        double t=now_sec(); if(t - t_last > 0.001){ (void)pump_tx_nonblock(cfd,&tx); t_last=t; }
    }
    // drain tx
    for(int i=0;i<100;i++){ if(ring_used(&tx)==0) break; if(pump_tx_nonblock(cfd,&tx)<0) break; struct timespec ts={0,1000000}; nanosleep(&ts,NULL);} 
    close(cfd); free(tx.buf); return 0; }

static int run_server(int port){ int srv=socket(AF_INET,SOCK_STREAM,0); if(srv<0) die("socket: %s",strerror(errno)); int one=1; setsockopt(srv,SOL_SOCKET,SO_REUSEADDR,&one,sizeof(one)); struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_addr.s_addr=htonl(INADDR_ANY); a.sin_port=htons((uint16_t)port); if(bind(srv,(struct sockaddr*)&a,sizeof(a))<0) die("bind: %s", strerror(errno)); if(listen(srv,64)<0) die("listen: %s", strerror(errno)); fprintf(stderr,"PFS native server listening on 0.0.0.0:%d\n",port); while(!g_stop){ struct sockaddr_in c; socklen_t cl=sizeof(c); int cfd=accept(srv,(struct sockaddr*)&c,&cl); if(cfd<0){ if(errno==EINTR) continue; if(errno==EAGAIN||errno==EWOULDBLOCK){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL); continue;} else die("accept: %s",strerror(errno)); } server_handle(cfd); } close(srv); return 0; }

static char* read_file(const char* path, size_t* out_len){ FILE* f=fopen(path,"rb"); if(!f) die("open %s: %s", path, strerror(errno)); fseek(f,0,SEEK_END); long n=ftell(f); if(n<0) die("ftell"); fseek(f,0,SEEK_SET); char* buf=(char*)malloc((size_t)n+1); if(!buf) die("malloc"); if(fread(buf,1,(size_t)n,f)!=(size_t)n) die("fread"); buf[n]=0; fclose(f); if(out_len) *out_len=(size_t)n; return buf; }

static unsigned long long json_get_ull(const char* json, const char* key, unsigned long long defv){ const char* p=strstr(json,key); if(!p) return defv; p=strchr(p,':'); if(!p) return defv; p++; while(*p==' '||*p=='\t') p++; unsigned long long v=0; while(*p>='0' && *p<='9'){ v = v*10 + (unsigned long long)(*p - '0'); p++; } return v; }

static int stream_recv_raw(int fd, unsigned long long size){ size_t buf_sz = 1<<20; uint8_t* buf=(uint8_t*)xaligned_alloc(4096, buf_sz); if(!buf) die("alloc recv buf"); unsigned long long got=0; double t0=now_sec(), tlast=t0; while(got < size){ size_t need = (size - got) < buf_sz ? (size_t)(size - got) : buf_sz; ssize_t r = recv(fd, buf, need, 0); if(r<0){ if(errno==EINTR) continue; free(buf); return -1; } if(r==0){ free(buf); return -1; } got += (unsigned long long)r; double tn = now_sec(); if(tn - tlast >= 1.0){ double mbps = (got/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"CLIENT RX avg: %.2f MB/s (%.1f MB)\n", mbps, got/(1024.0*1024.0)); tlast = tn; } } free(buf); return 0; }

static int run_client(const char* host, int port, const char* blueprint_path, unsigned long long opt_stream_size, unsigned long long opt_chunk_kb){ int fd=socket(AF_INET,SOCK_STREAM,0); if(fd<0) die("socket: %s",strerror(errno)); struct sockaddr_in a; memset(&a,0,sizeof(a)); a.sin_family=AF_INET; a.sin_port=htons((uint16_t)port); if(inet_pton(AF_INET,host,&a.sin_addr)<=0) die("inet_pton %s",host); if(connect(fd,(struct sockaddr*)&a,sizeof(a))<0) die("connect: %s",strerror(errno)); /* blocking socket */ tx_ring_t tx=ring_new(1<<20);
    const char* hello="{\"client\":\"PacketFS-Native\",\"features\":[\"file-transfer\"]}"; if(send_frame(fd,&tx,MSG_HELLO,(const uint8_t*)hello,(uint32_t)strlen(hello))<0) die("send hello"); pump_tx_nonblock(fd,&tx);
    // recv hello
    uint32_t t,l; uint8_t* body=NULL; if(recv_frame(fd,&t,&body,&l)<0) die("recv hello"); if(t!=MSG_HELLO){ free(body); die("unexpected msg %u", t);} free(body);
    // Mode selection: if blueprint_path is non-empty and not "-", send blueprint; otherwise stream test via FILE_REQUEST
    if(blueprint_path && strcmp(blueprint_path,"-")!=0){
        size_t blen=0; char* bjson = read_file(blueprint_path,&blen);
        if(send_frame(fd,&tx,MSG_BLUEPRINT_REQUEST,(const uint8_t*)bjson,(uint32_t)blen)<0) die("send blueprint"); free(bjson);
        for(;;){ pump_tx_nonblock(fd,&tx); int r=recv_frame(fd,&t,&body,&l); if(r==0){ if(t==MSG_FILE_COMPLETE){ fprintf(stderr,"server ack: %.*s\n", (int)l, (const char*)body); free(body); break; } else if(t==MSG_ERROR){ fprintf(stderr,"server error: %.*s\n", (int)l, (const char*)body); free(body); break; } else { free(body); } } else { struct timespec ts={0,1000000}; nanosleep(&ts,NULL);} if(g_stop) break; }
    } else {
        // Stream test: request size (bytes) via CLI-controlled values
        unsigned long long sz = (opt_stream_size? opt_stream_size : 419430400ULL);
        unsigned long long ckb = (opt_chunk_kb? opt_chunk_kb : 64ULL);
        char req[128]; int n = snprintf(req,sizeof(req),"{\"size\": %llu, \"chunk_kb\": %llu}",(unsigned long long)sz,(unsigned long long)ckb);
        if(n<0 || n>=(int)sizeof(req)) die("req snprintf");
        if(send_frame(fd,&tx,MSG_FILE_REQUEST,(const uint8_t*)req,(uint32_t)n)<0) die("send file request");
        pump_tx_nonblock(fd,&tx); // ensure FILE_REQUEST leaves the TX ring immediately
        unsigned long long total=0; double t0=now_sec(), tlast=t0; for(;;){ int r=recv_frame(fd,&t,&body,&l); if(r<0) die("recv stream"); if(t==MSG_FILE_STREAM_START){ unsigned long long sz2 = json_get_ull((const char*)body, "\"size\"", 0ULL); free(body); if(sz2==0ULL) die("invalid stream size"); if(stream_recv_raw(fd, sz2)<0) die("stream_recv_raw"); continue; } else if(t==MSG_FILE_DATA){ total += l; free(body); } else if(t==MSG_FILE_COMPLETE){ fprintf(stderr,"stream complete: %.*s\n", (int)l, (const char*)body); free(body); break; } else { free(body); }
            double tn=now_sec(); if(tn - tlast >= 1.0){ double mbps = (total/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"CLIENT RX avg: %.2f MB/s (%.1f MB)\n", mbps, total/(1024.0*1024.0)); tlast=tn; }
        }
    }
    close(fd); free(tx.buf); return 0; }

static int run_server_stream(int cfd, const char* json){ // parse size and chunk_kb
    unsigned long long size = json_get_ull(json, "\"size\"", 419430400ULL);
    unsigned long long chunk_kb = json_get_ull(json, "\"chunk_kb\"", 64ULL);
    if(chunk_kb==0ULL) return run_server_stream_raw(cfd, size);
    size_t chunk = (size_t)(chunk_kb*1024ULL); if(chunk<4096) chunk=4096; if(chunk> (8*1024*1024)) chunk = 8*1024*1024; 
    uint8_t* buf = (uint8_t*)xaligned_alloc(4096, chunk); if(!buf) die("alloc stream buf"); for(size_t i=0;i<chunk;i++) buf[i]=(uint8_t)(i*1315423911u);
    tx_ring_t tx = ring_new(1<<20);
    unsigned long long sent=0; double t0=now_sec(), tlast=t0;
    while(sent < size){ size_t n = (size - sent) < (unsigned long long)chunk ? (size_t)(size - sent) : chunk; if(send_frame(cfd,&tx,MSG_FILE_DATA,buf,n)<0) break; (void)pump_tx_nonblock(cfd,&tx); sent += n; double tn=now_sec(); if(tn - tlast >= 1.0){ double mbps = (sent/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"SERVER TX avg: %.2f MB/s (%.1f MB)\n", mbps, sent/(1024.0*1024.0)); tlast=tn; } }
    const char* done="{\"status\":\"complete\"}"; (void)send_frame(cfd,&tx,MSG_FILE_COMPLETE,(const uint8_t*)done,(uint32_t)strlen(done)); (void)pump_tx_nonblock(cfd,&tx);
    for(int i=0;i<100;i++){ if(ring_used(&tx)==0) break; if(pump_tx_nonblock(cfd,&tx)<0) break; struct timespec ts={0,1000000}; nanosleep(&ts,NULL);} 
    free(tx.buf); free(buf); return 0; }

static int run_server_stream_raw(int cfd, unsigned long long size){ tx_ring_t tx = ring_new(1<<20); char start[96]; int n = snprintf(start, sizeof(start), "{\"status\":\"stream-start\",\"size\": %llu}", (unsigned long long)size); if(n<0) n=0; (void)send_frame(cfd,&tx,MSG_FILE_STREAM_START,(const uint8_t*)start,(uint32_t)n); (void)pump_tx_nonblock(cfd,&tx); size_t block = 1<<20; uint8_t* buf=(uint8_t*)xaligned_alloc(4096, block); if(!buf) die("alloc stream raw buf"); for(size_t i=0;i<block;i++) buf[i]=(uint8_t)(i*1315423911u); unsigned long long sent=0; double t0=now_sec(), tlast=t0; while(sent < size){ size_t tosend = (size - sent) < (unsigned long long)block ? (size_t)(size - sent) : block; size_t remain = tosend; while(remain>0){ size_t wrote = ring_write(&tx, buf, remain); if(wrote==0){ int pr=pump_tx_nonblock(cfd,&tx); if(pr<0){ free(buf); free(tx.buf); return -1; } if(pr==0){ struct timespec ts={0,1000000}; nanosleep(&ts,NULL);} } else { remain -= wrote; } } (void)pump_tx_nonblock(cfd,&tx); sent += tosend; double tn=now_sec(); if(tn - tlast >= 1.0){ double mbps = (sent/(1024.0*1024.0))/(tn - t0); fprintf(stderr,"SERVER TX avg: %.2f MB/s (%.1f MB)\n", mbps, sent/(1024.0*1024.0)); tlast=tn; } } const char* done="{\"status\":\"complete\"}"; (void)send_frame(cfd,&tx,MSG_FILE_COMPLETE,(const uint8_t*)done,(uint32_t)strlen(done)); (void)pump_tx_nonblock(cfd,&tx); for(int i=0;i<100;i++){ if(ring_used(&tx)==0) break; if(pump_tx_nonblock(cfd,&tx)<0) break; struct timespec ts={0,1000000}; nanosleep(&ts,NULL);} free(buf); free(tx.buf); return 0; }

int main(int argc, char** argv){ signal(SIGINT,on_sigint); const char* mode=NULL; const char* host="127.0.0.1"; int port=8337; const char* blueprint="dev/wip/native/sample_blueprint.json"; unsigned long long stream_size=419430400ULL; unsigned long long stream_chunk_kb=64ULL; for(int i=1;i<argc;i++){ if(!strcmp(argv[i],"--mode") && i+1<argc) mode=argv[++i]; else if(!strcmp(argv[i],"--port") && i+1<argc) port=atoi(argv[++i]); else if(!strcmp(argv[i],"--host") && i+1<argc) host=argv[++i]; else if(!strcmp(argv[i],"--blueprint-file") && i+1<argc) blueprint=argv[++i]; else if(!strcmp(argv[i],"--stream-size") && i+1<argc) stream_size=strtoull(argv[++i],NULL,10); else if(!strcmp(argv[i],"--stream-chunk-kb") && i+1<argc) stream_chunk_kb=strtoull(argv[++i],NULL,10); else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){ printf("Usage:\n  server: --mode server --port P\n  client: --mode client --host H --port P --blueprint-file path.json (use '-' to request stream test) [--stream-size BYTES --stream-chunk-kb KB]\n"); return 0;} }
    if(!mode) die("--mode required (server|client)"); if(!strcmp(mode,"server")) return run_server(port); else if(!strcmp(mode,"client")) return run_client(host,port,blueprint,stream_size,stream_chunk_kb); else die("unknown mode"); }

