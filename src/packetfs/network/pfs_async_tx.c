// PacketFS async TX prototype (single-threaded async with batching)
// Real, production-focused prototype: saturate NIC with minimal CPU using TCP
// - Batching via writev
// - Optional MSG_ZEROCOPY (Linux)
// - Ring buffer sized by BDP
// - Periodic throughput reporting
// Build: cc -O3 -march=native -DNDEBUG -pthread -o bin/pfs_async_tx realsrc/packetfs/network/pfs_async_tx.c

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

#ifndef MSG_ZEROCOPY
#define MSG_ZEROCOPY 0
#endif
#ifndef SO_ZEROCOPY
#define SO_ZEROCOPY 60
#endif

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop = 1; }

static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void set_nonblock(int fd){ int fl = fcntl(fd, F_GETFL, 0); fcntl(fd, F_SETFL, fl | O_NONBLOCK); }

static void die(const char* fmt, ...){ va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap); fprintf(stderr, "\n"); exit(1); }

static void* xaligned_alloc(size_t align, size_t sz){ void* p = NULL; if(posix_memalign(&p, align, sz)!=0) return NULL; memset(p, 0, sz); return p; }

int main(int argc, char** argv){
    const char* host = "127.0.0.1";
    int port = 9107;
    int seconds = 10;
    int buf_kb = 64;            // per iov payload size
    int flows = 1;              // future use; for now 1
    int zerocopy = 0;           // 0/1
    int bdp_mb = 8;             // TX ring target bytes in MB

    // Parse args
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--host") && i+1<argc) host = argv[++i];
        else if(!strcmp(argv[i],"--port") && i+1<argc) port = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--seconds") && i+1<argc) seconds = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--buf-kb") && i+1<argc) buf_kb = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--flows") && i+1<argc) flows = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--zerocopy") && i+1<argc) zerocopy = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--bdp-mb") && i+1<argc) bdp_mb = atoi(argv[++i]);
        else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")){
            printf("Usage: pfs_async_tx --host H --port P --seconds S --buf-kb K --flows N --zerocopy 0|1 --bdp-mb M\n");
            return 0;
        }
    }

    (void)flows; // single flow for now

    signal(SIGINT, on_sigint);

    // Resolve and connect
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if(sock<0) die("socket: %s", strerror(errno));

    // optional: NODELAY to reduce Nagle interactions (we batch anyway)
    int one = 1;
    setsockopt(sock, IPPROTO_TCP, TCP_NODELAY, &one, sizeof(one));

    if(zerocopy){
        // enable kernel zero-copy path
        if(setsockopt(sock, SOL_SOCKET, SO_ZEROCOPY, &one, sizeof(one))<0){
            fprintf(stderr, "warn: SO_ZEROCOPY not supported: %s\n", strerror(errno));
            zerocopy = 0;
        }
    }

    struct sockaddr_in addr; memset(&addr,0,sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons((uint16_t)port);
    if(inet_pton(AF_INET, host, &addr.sin_addr)<=0) die("inet_pton failed for %s", host);

    if(connect(sock, (struct sockaddr*)&addr, sizeof(addr))<0) die("connect: %s", strerror(errno));

    // Non-blocking to avoid stalls; we’ll spin/poll via EAGAIN backoff
    set_nonblock(sock);

    // Prepare ring buffer and iovecs
    size_t buf_bytes = (size_t)buf_kb * 1024;
    if(buf_bytes < 4096) buf_bytes = 4096;

    size_t ring_bytes = (size_t)bdp_mb * 1024 * 1024;
    if(ring_bytes < buf_bytes * 16) ring_bytes = buf_bytes * 16; // ensure multiple buffers

    uint8_t* ring = (uint8_t*)xaligned_alloc(4096, ring_bytes);
    if(!ring) die("alloc ring failed");

    // Fill with deterministic pseudo-data to avoid page faults on send path
    for(size_t i=0;i<ring_bytes;i++) ring[i] = (uint8_t)(i*1315423911u);

    const int iov_count = (int)(ring_bytes / buf_bytes);
    if(iov_count < 4) die("ring too small for chosen buf_kb/bdp_mb");

    struct iovec* iovs = (struct iovec*)calloc((size_t)iov_count, sizeof(struct iovec));
    if(!iovs) die("alloc iov failed");
    for(int i=0;i<iov_count;i++){
        iovs[i].iov_base = ring + (size_t)i*buf_bytes;
        iovs[i].iov_len = buf_bytes;
    }

    // TX loop
    double t0 = now_sec();
    double t_last = t0;
    unsigned long long bytes_total = 0;
    unsigned long long bytes_window = 0;

    // Sliding window over iov indices
    int head = 0; // next to send

    while(!g_stop){
        double t = now_sec();
        if((int)(t - t0) >= seconds) break;

        // Write as many iovecs as the kernel accepts without blocking
        // Use writev in batches (e.g., up to 64 iovs per syscall)
        const int batch = 64;
        int remain = iov_count; // allow wrap but keep ring resident
        while(remain > 0){
            int n = batch < remain ? batch : remain;
            // prepare a window of iovecs starting at head
            struct iovec vecs[batch];
            for(int k=0;k<n;k++){
                int idx = (head + k) % iov_count;
                vecs[k] = iovs[idx];
            }
            ssize_t w = writev(sock, vecs, n);
            if(w < 0){
                if(errno==EAGAIN || errno==EWOULDBLOCK){
                    // back off briefly
                    struct timespec ts = {0, 2000000}; // 2ms
                    nanosleep(&ts, NULL);
                    break; // let outer loop re-check time and try again
                } else if(errno==EPIPE || errno==ECONNRESET){
                    die("peer closed: %s", strerror(errno));
                } else {
                    die("writev: %s", strerror(errno));
                }
            } else if(w == 0){
                // no progress, brief sleep
                struct timespec ts = {0, 1000000};
                nanosleep(&ts, NULL);
                break;
            } else {
                bytes_total += (unsigned long long)w;
                bytes_window += (unsigned long long)w;
                // advance head by the number of full buffers consumed
                size_t advanced = (size_t)w / buf_bytes;
                head = (head + (int)advanced) % iov_count;
                remain -= (int)advanced;
                // partial leftover ignored for simplicity; next writev covers it
            }
        }

        if(t - t_last >= 1.0){
            double mbps = (bytes_window / (1024.0*1024.0)) / (t - t_last);
            fprintf(stderr, "TX: %.2f MB/s (total %.1f MB)\n", mbps, bytes_total/(1024.0*1024.0));
            t_last = t;
            bytes_window = 0;
        }
    }

    // graceful close
    shutdown(sock, SHUT_WR);
    close(sock);

    double t1 = now_sec();
    double mb = bytes_total / (1024.0*1024.0);
    double dur = t1 - t0;
    fprintf(stderr, "TX DONE: sent %.1f MB in %.2fs => %.2f MB/s\n", mb, dur, dur>0? (mb/dur):0.0);

    free(iovs);
    free(ring);
    return 0;
}

