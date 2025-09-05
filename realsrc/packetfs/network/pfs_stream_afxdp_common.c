#define _GNU_SOURCE
#include <errno.h>
#include <net/if.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <xdp/xsk.h>
#include "pfs_stream_afxdp.h"

int pfs_xdp_umem_create(PfsXdpUmem* u, size_t size, uint32_t frame_size, uint32_t frame_count){
    memset(u, 0, sizeof(*u));
    u->frame_size = frame_size;
    u->frame_count = frame_count;
    u->size = (size_t)frame_size * frame_count;
    void* buf = NULL;
    int ret = posix_memalign(&buf, getpagesize(), u->size);
    if(ret != 0) { fprintf(stderr, "umem alloc: %s\n", strerror(ret)); return -1; }
    if(mlock(buf, u->size) != 0){ fprintf(stderr, "umem mlock: %s\n", strerror(errno)); free(buf); return -1; }
    struct xsk_umem_config cfg = {
        .fill_size = frame_count,
        .comp_size = frame_count,
        .frame_size = frame_size,
        .frame_headroom = 0
    };
    if(xsk_umem__create(&u->umem, buf, u->size, &u->fq, &u->cq, &cfg) != 0){
        fprintf(stderr, "xsk_umem__create failed: %s\n", strerror(errno));
        munlock(buf, u->size); free(buf); return -1;
    }
    u->buffer = buf; return 0;
}

void pfs_xdp_umem_destroy(PfsXdpUmem* u){
    if(!u) return; if(u->umem) xsk_umem__delete(u->umem); if(u->buffer){ munlock(u->buffer, u->size); free(u->buffer); }
    memset(u, 0, sizeof(*u));
}

int pfs_xdp_socket_create(PfsXdpSocket* s, PfsXdpUmem* u, const char* ifname, uint32_t queue_id, int rx, int tx, int zerocopy){
    memset(s, 0, sizeof(*s)); s->umem = u; s->queue_id = queue_id; s->ifindex = if_nametoindex(ifname);
    if(s->ifindex == 0){ fprintf(stderr, "if_nametoindex(%s): %s\n", ifname, strerror(errno)); return -1; }
    struct xsk_socket_config cfg = {
        .rx_size = rx ? u->frame_count : 0,
        .tx_size = tx ? u->frame_count : 0,
        .libbpf_flags = 0,
        .xdp_flags = 0,
        .bind_flags = (zerocopy ? XDP_ZEROCOPY : 0) | XDP_USE_NEED_WAKEUP
    };
    if(xsk_socket__create(&s->xsk, ifname, queue_id, u->umem, rx?&s->rx:NULL, tx?&s->tx:NULL, &cfg) != 0){
        fprintf(stderr, "xsk_socket__create(%s q%u) failed: %s\n", ifname, queue_id, strerror(errno)); return -1;
    }
    s->outstanding_tx = 0; return 0;
}

void pfs_xdp_socket_destroy(PfsXdpSocket* s){ if(!s) return; if(s->xsk) xsk_socket__delete(s->xsk); memset(s,0,sizeof(*s)); }

