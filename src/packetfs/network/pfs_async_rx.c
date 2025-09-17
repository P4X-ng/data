// PacketFS async RX prototype (single-threaded, high-throughput sink)
// - Accepts one connection and reads into a page-aligned buffer
// - Reports MB/s every second
// Build: cc -O3 -march=native -DNDEBUG -pthread -o bin/pfs_async_rx realsrc/packetfs/network/pfs_async_rx.c

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
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop = 1; }

static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void die(const char* fmt, ...){ va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap); fprintf(stderr, "\n"); exit(1); }

static void* xaligned_alloc(size_t align, size_t sz){ void* p = NULL; if(posix_memalign(&p, align, sz)!=0) return NULL; memset(p, 0, sz); return p; }

int main(int argc, char** argv){
    int port = 9107;
    int buf_kb = 256; // RX buffer per read

    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--port") && i+1<argc) port = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--buf-kb") && i+1<argc) buf_kb = atoi(argv[++i]);
        else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")){
            printf("Usage: pfs_async_rx --port P --buf-kb K\n");
            return 0;
        }
    }

    signal(SIGINT, on_sigint);

    int srv = socket(AF_INET, SOCK_STREAM, 0);
    if(srv<0) die("socket: %s", strerror(errno));
    int one = 1;
    setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));

    struct sockaddr_in addr; memset(&addr,0,sizeof(addr));
    addr.sin_family = AF_INET; addr.sin_addr.s_addr = htonl(INADDR_ANY); addr.sin_port = htons((uint16_t)port);
    if(bind(srv, (struct sockaddr*)&addr, sizeof(addr))<0) die("bind: %s", strerror(errno));
    if(listen(srv, 16)<0) die("listen: %s", strerror(errno));

    fprintf(stderr, "RX listening on 0.0.0.0:%d\n", port);

    struct sockaddr_in cli; socklen_t clilen = sizeof(cli);
    int cli_fd = accept(srv, (struct sockaddr*)&cli, &clilen);
    if(cli_fd<0) die("accept: %s", strerror(errno));

    // enlarge socket buffers
    int rcvbuf = 8*1024*1024; // 8MB
    setsockopt(cli_fd, SOL_SOCKET, SO_RCVBUF, &rcvbuf, sizeof(rcvbuf));

    size_t buf_bytes = (size_t)buf_kb * 1024;
    if(buf_bytes < 4096) buf_bytes = 4096;
    uint8_t* buf = (uint8_t*)xaligned_alloc(4096, buf_bytes);
    if(!buf) die("alloc rx buf failed");

    double t0 = now_sec(), t_last=t0;
    unsigned long long total=0, window=0;

    while(!g_stop){
        ssize_t r = recv(cli_fd, buf, buf_bytes, 0);
        if(r<0){
            if(errno==EAGAIN || errno==EWOULDBLOCK){
                struct timespec ts = {0, 1000000}; nanosleep(&ts,NULL); continue;
            } else die("recv: %s", strerror(errno));
        } else if(r==0){
            break; // peer closed
        } else {
            total += (unsigned long long)r;
            window += (unsigned long long)r;
        }
        double t = now_sec();
        if(t - t_last >= 1.0){
            double mbps = (window/(1024.0*1024.0))/(t - t_last);
            fprintf(stderr, "RX: %.2f MB/s (total %.1f MB)\n", mbps, total/(1024.0*1024.0));
            t_last = t; window = 0;
        }
    }

    close(cli_fd); close(srv);
    double t1 = now_sec();
    double mb = total/(1024.0*1024.0); double dur = t1-t0;
    fprintf(stderr, "RX DONE: %.1f MB in %.2fs => %.2f MB/s\n", mb, dur, dur>0? (mb/dur):0.0);

    free(buf);
    return 0;
}

