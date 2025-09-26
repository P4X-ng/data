#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include "pfs_afxdp.h"

static const char* mstr(int m){ return m==PFS_AFXDP_MODE_DRV?"drv":(m==PFS_AFXDP_MODE_SKB?"skb":"auto"); }

int main(int argc, char** argv){
    const char* ifname=NULL; unsigned q=0; unsigned fs=2048; unsigned nd=4096; int require_zc=1; int mode_req=PFS_AFXDP_MODE_DRV;
    for(int i=1;i<argc;i++){
        if(!strcmp(argv[i],"--iface") && i+1<argc) ifname=argv[++i];
        else if(!strcmp(argv[i],"--queue") && i+1<argc) q=(unsigned)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--frame-size") && i+1<argc) fs=(unsigned)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--ndescs") && i+1<argc) nd=(unsigned)strtoul(argv[++i],NULL,10);
        else if(!strcmp(argv[i],"--require-zc") && i+1<argc) require_zc=atoi(argv[++i]);
        else if(!strcmp(argv[i],"--mode") && i+1<argc){ const char* m=argv[++i]; if(!strcmp(m,"drv")) mode_req=PFS_AFXDP_MODE_DRV; else if(!strcmp(m,"skb")) mode_req=PFS_AFXDP_MODE_SKB; else mode_req=PFS_AFXDP_MODE_AUTO; }
        else if(!strcmp(argv[i],"-h")||!strcmp(argv[i],"--help")){
            fprintf(stderr,"Usage: %s --iface IFACE [--queue Q=0] [--frame-size 2048] [--ndescs 4096] [--require-zc 1] [--mode drv|skb|auto]\n", argv[0]);
            return 0;
        }
    }
    if(!ifname){ fprintf(stderr,"--iface required\n"); return 2; }
    pfs_afxdp_handle h = pfs_afxdp_open(ifname, q, fs, nd, require_zc, mode_req, 50);
    if(!h){ perror("pfs_afxdp_open"); return 1; }
    int zc = pfs_afxdp_is_zerocopy(h); int mode = pfs_afxdp_mode(h);
    fprintf(stderr, "iface=%s queue=%u frame=%u ndesc=%u mode=%s zerocopy=%d\n", ifname, q, fs, nd, mstr(mode), zc);
    pfs_afxdp_close(h);
    return 0;
}

