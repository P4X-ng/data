#define _GNU_SOURCE
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <signal.h>
#include <time.h>
#include "pfs_afxdp.h"

static volatile sig_atomic_t g_stop = 0;
static void on_sigint(int sig){ (void)sig; g_stop = 1; }
static double now_sec(){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec/1e9; }

static void usage(const char* argv0){
    fprintf(stderr,
        "Usage: %s --iface IFACE [--queue Q=0] [--frame-size FS=2048] [--ndescs N=4096]\\n"
        "          [--require-zc 1] [--mode auto|drv|skb] [--busy-poll-ms MS=50] [--duration-s S=5]\\n",
        argv0);
}

static int parse_mode(const char* s){ if(!s) return PFS_AFXDP_MODE_DRV; if(!strcmp(s,"drv")) return PFS_AFXDP_MODE_DRV; if(!strcmp(s,"skb")) return PFS_AFXDP_MODE_SKB; return PFS_AFXDP_MODE_AUTO; }

int main(int argc, char** argv){
    signal(SIGINT, on_sigint);
    const char* ifname = NULL; uint32_t queue=0; uint32_t frame_size=2048; uint32_t ndescs=4096;
    int require_zc = 1; int mode_req = PFS_AFXDP_MODE_DRV; int busy_ms=50; double duration=5.0;

    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--iface") && i+1<argc) ifname = argv[++i];
        else if(!strcmp(argv[i],"--queue") && i+1<argc) queue = (uint32_t)strtoul(argv[++i], NULL, 10);
        else if(!strcmp(argv[i],"--frame-size") && i+1<argc) frame_size = (uint32_t)strtoul(argv[++i], NULL, 10);
        else if(!strcmp(argv[i],"--ndescs") && i+1<argc) ndescs = (uint32_t)strtoul(argv[++i], NULL, 10);
        else if(!strcmp(argv[i],"--require-zc") && i+1<argc) require_zc = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--mode") && i+1<argc) mode_req = parse_mode(argv[++i]);
        else if(!strcmp(argv[i],"--busy-poll-ms") && i+1<argc) busy_ms = atoi(argv[++i]);
        else if(!strcmp(argv[i],"--duration-s") && i+1<argc) duration = atof(argv[++i]);
        else if(!strcmp(argv[i],"-h") || !strcmp(argv[i],"--help")) { usage(argv[0]); return 0; }
    }
    if(!ifname){ usage(argv[0]); return 2; }

    pfs_afxdp_handle h = pfs_afxdp_open(ifname, queue, frame_size, ndescs, require_zc, mode_req, busy_ms);
    if(!h){ perror("pfs_afxdp_open"); fprintf(stderr, "[ERR] open failed (require_zc=%d)\n", require_zc); return 1; }

    int zc = pfs_afxdp_is_zerocopy(h); int mode = pfs_afxdp_mode(h);
    fprintf(stderr, "[TX] iface=%s q=%u mode=%s zerocopy=%d frame=%u ndesc=%u\n",
            ifname, queue, (mode==PFS_AFXDP_MODE_DRV?"drv":(mode==PFS_AFXDP_MODE_SKB?"skb":"auto")), zc, frame_size, ndescs);

    (void)pfs_afxdp_fill(h, ndescs);

    double t0=now_sec(), tlast=t0; uint64_t frames=0;
    while(!g_stop){
        if(duration>0 && (now_sec()-t0) >= duration) break;
        int s = pfs_afxdp_tx_burst(h, frame_size - 64, 64);
        if(s>0) frames += (uint64_t)s;
        double tn=now_sec(); if((tn - tlast) >= 0.5){ double fps = frames/(tn - t0 + 1e-9); fprintf(stderr, "[TX] frames=%llu fps=%.0f\n", (unsigned long long)frames, fps); tlast=tn; }
    }

    double t1=now_sec(); double fps = frames/(t1 - t0 + 1e-9);
    fprintf(stderr, "[TX DONE] frames=%llu elapsed=%.3f s fps=%.0f zerocopy=%d mode=%s\n",
            (unsigned long long)frames, (t1-t0), fps, zc,
            (mode==PFS_AFXDP_MODE_DRV?"drv":(mode==PFS_AFXDP_MODE_SKB?"skb":"auto")));

    pfs_afxdp_close(h);
    return 0;
}

