#define _GNU_SOURCE
#include <errno.h>
#include <net/if.h>
#include <poll.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <unistd.h>

#include <bpf/libbpf.h>
#include <xdp/xsk.h>

#include "pfs_afxdp.h"

struct pfs_afxdp_state {
    struct xsk_umem* umem;
    void*            buf;
    size_t           umem_size;
    struct xsk_ring_prod fq;
    struct xsk_ring_cons cq;

    struct xsk_socket* xsk;
    struct xsk_ring_cons rx;
    struct xsk_ring_prod tx;

    uint32_t frame_size;
    uint32_t frame_count;
    uint32_t ndescs;

    int ifindex;
    uint32_t queue;
    int mode; // PFS_AFXDP_MODE_DRV or PFS_AFXDP_MODE_SKB
    int zc_active;

    uint32_t outstanding_tx;
    int busy_poll_ms;
};

static inline uint64_t frame_addr(struct pfs_afxdp_state* s, uint32_t idx){ return (uint64_t)idx * s->frame_size; }
static inline void* frame_ptr(struct pfs_afxdp_state* s, uint64_t addr){ return (uint8_t*)s->buf + addr; }

pfs_afxdp_handle pfs_afxdp_open(const char* ifname,
                                uint32_t queue,
                                uint32_t frame_size,
                                uint32_t ndescs,
                                int require_zc,
                                int mode_req,
                                int busy_poll_ms)
{
    if(!ifname || frame_size == 0 || ndescs == 0) return NULL;
    struct pfs_afxdp_state* s = calloc(1, sizeof(*s));
    if(!s) return NULL;

    s->ifindex = if_nametoindex(ifname);
    if(s->ifindex == 0){ free(s); return NULL; }
    s->queue = queue;
    s->frame_size = frame_size;
    s->frame_count = ndescs; // simple mapping
    s->ndescs = ndescs;
    s->busy_poll_ms = busy_poll_ms;

    // UMEM allocation (page-aligned) and lock into memory
    s->umem_size = (size_t)s->frame_size * s->frame_count;
    void* buf = NULL;
    int ret = posix_memalign(&buf, getpagesize(), s->umem_size);
    if(ret != 0){ free(s); return NULL; }
    if(mlock(buf, s->umem_size) != 0){ free(buf); free(s); return NULL; }

    struct xsk_umem_config ucfg = {
        .fill_size = s->frame_count,
        .comp_size = s->frame_count,
        .frame_size = s->frame_size,
        .frame_headroom = 0,
    };
    if(xsk_umem__create(&s->umem, buf, s->umem_size, &s->fq, &s->cq, &ucfg) != 0){
        munlock(buf, s->umem_size); free(buf); free(s); return NULL;
    }
    s->buf = buf;

    // Socket config - require native by default, zerocopy requested by default
    struct xsk_socket_config cfg = {
        .rx_size = s->ndescs,
        .tx_size = s->ndescs,
        .libbpf_flags = 0,
        .xdp_flags = 0,
        .bind_flags = XDP_USE_NEED_WAKEUP
    };
    if(mode_req == PFS_AFXDP_MODE_DRV) cfg.xdp_flags = XDP_FLAGS_DRV_MODE;
    else if(mode_req == PFS_AFXDP_MODE_SKB) cfg.xdp_flags = XDP_FLAGS_SKB_MODE;
    else cfg.xdp_flags = XDP_FLAGS_DRV_MODE; // prefer native

#ifdef XDP_ZEROCOPY
    if(require_zc) cfg.bind_flags |= XDP_ZEROCOPY;
#else
    // Kernel headers without XDP_ZEROCOPY define -> cannot satisfy require_zc
    if(require_zc){ xsk_umem__delete(s->umem); munlock(buf, s->umem_size); free(buf); free(s); return NULL; }
#endif

    if(xsk_socket__create(&s->xsk, ifname, s->queue, s->umem, &s->rx, &s->tx, &cfg) != 0){
        int e = errno;
        if(require_zc){ // fail fast; caller wants zerocopy only
            xsk_umem__delete(s->umem); munlock(buf, s->umem_size); free(buf); free(s); errno = e; return NULL;
        }
        // Try fallback: SKB + copy
        cfg.xdp_flags = XDP_FLAGS_SKB_MODE;
#ifdef XDP_ZEROCOPY
        cfg.bind_flags &= ~XDP_ZEROCOPY;
#endif
        if(xsk_socket__create(&s->xsk, ifname, s->queue, s->umem, &s->rx, &s->tx, &cfg) != 0){
            e = errno; xsk_umem__delete(s->umem); munlock(buf, s->umem_size); free(buf); free(s); errno = e; return NULL;
        }
    }

    s->mode = (cfg.xdp_flags & XDP_FLAGS_SKB_MODE) ? PFS_AFXDP_MODE_SKB : PFS_AFXDP_MODE_DRV;
#ifdef XDP_ZEROCOPY
    s->zc_active = (cfg.bind_flags & XDP_ZEROCOPY) ? 1 : 0;
#else
    s->zc_active = 0;
#endif

    // Busy-poll tuning (optional)
#ifdef SO_PREFER_BUSY_POLL
    if(s->busy_poll_ms > 0){
        int one = 1; int ms = s->busy_poll_ms; int fd = xsk_socket__fd(s->xsk);
        (void)setsockopt(fd, SOL_SOCKET, SO_PREFER_BUSY_POLL, &one, sizeof(one));
#ifdef SO_BUSY_POLL
        (void)setsockopt(fd, SOL_SOCKET, SO_BUSY_POLL, &ms, sizeof(ms));
#endif
    }
#endif

    return (pfs_afxdp_handle)s;
}

int pfs_afxdp_is_zerocopy(pfs_afxdp_handle h){ struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return 0; return s->zc_active ? 1 : 0; }
int pfs_afxdp_mode(pfs_afxdp_handle h){ struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return 0; return s->mode; }

int pfs_afxdp_fill(pfs_afxdp_handle h, uint32_t count){
    struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return -1;
    uint32_t idx; unsigned int n = xsk_ring_prod__reserve(&s->fq, count, &idx);
    for(unsigned int i=0;i<n;i++){ *xsk_ring_prod__fill_addr(&s->fq, idx+i) = frame_addr(s, i % s->frame_count); }
    xsk_ring_prod__submit(&s->fq, n);
    return (int)n;
}

int pfs_afxdp_poll(pfs_afxdp_handle h, int timeout_ms){
    struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return -1;
    struct pollfd pfd = { .fd = xsk_socket__fd(s->xsk), .events = POLLIN | POLLOUT };
    return poll(&pfd, 1, timeout_ms);
}

int pfs_afxdp_rx_burst(pfs_afxdp_handle h, uint32_t max_frames, uint64_t* bytes_out){
    struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return -1;
    if(bytes_out) *bytes_out = 0;
    uint32_t idx; unsigned int r = xsk_ring_cons__peek(&s->rx, max_frames, &idx);
    for(unsigned int i=0;i<r;i++){
        const struct xdp_desc* rx = xsk_ring_cons__rx_desc(&s->rx, idx + i);
        if(bytes_out) *bytes_out += rx->len;
    }
    xsk_ring_cons__release(&s->rx, r);

    // recycle back to FILL
    uint32_t pushed=0; while(pushed<r){
        uint32_t idx_fq; unsigned int m = xsk_ring_prod__reserve(&s->fq, r-pushed, &idx_fq);
        if(!m) break;
        for(unsigned int j=0;j<m;j++){
            *xsk_ring_prod__fill_addr(&s->fq, idx_fq + j) = frame_addr(s, (idx + pushed + j) % s->frame_count);
        }
        xsk_ring_prod__submit(&s->fq, m);
        pushed += m;
    }
    return (int)r;
}

int pfs_afxdp_tx_burst(pfs_afxdp_handle h, uint32_t frame_len, uint32_t frames){
    struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return -1;
    uint32_t sent=0;
    while(sent < frames){
        uint32_t idx; unsigned int r = xsk_ring_prod__reserve(&s->tx, frames - sent, &idx);
        if(!r){
            // reaps
            uint32_t cqi; unsigned int c = xsk_ring_cons__peek(&s->cq, 64, &cqi);
            if(c){ xsk_ring_cons__release(&s->cq, c); if(s->outstanding_tx >= c) s->outstanding_tx -= c; }
            // nudge kernel
            sendto(xsk_socket__fd(s->xsk), NULL, 0, MSG_DONTWAIT, NULL, 0);
            break;
        }
        for(unsigned int i=0;i<r;i++){
            uint64_t addr = frame_addr(s, (idx + i) % s->frame_count);
            struct xdp_desc* txd = xsk_ring_prod__tx_desc(&s->tx, idx + i);
            txd->addr = addr; txd->len = frame_len <= s->frame_size ? frame_len : s->frame_size;
            // payload can be pre-filled in buf if needed; leaving zeroed is fine for link test
        }
        xsk_ring_prod__submit(&s->tx, r); s->outstanding_tx += r; sent += r;
    }
    return (int)sent;
}

void pfs_afxdp_close(pfs_afxdp_handle h){
    struct pfs_afxdp_state* s = (struct pfs_afxdp_state*)h; if(!s) return;
    if(s->xsk) xsk_socket__delete(s->xsk);
    if(s->umem){ xsk_umem__delete(s->umem); }
    if(s->buf){ munlock(s->buf, s->umem_size); free(s->buf); }
    free(s);
}

