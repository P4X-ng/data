#pragma once
#include <stdint.h>
#include <stddef.h>
#include <xdp/xsk.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    struct xsk_umem* umem;
    void* buffer;
    size_t size;
    struct xsk_ring_prod fq;
    struct xsk_ring_cons cq;
    uint32_t frame_size;
    uint32_t frame_count;
} PfsXdpUmem;

typedef enum {
    PFS_XDP_MODE_AUTO = 0,
    PFS_XDP_MODE_DRV  = 1,
    PFS_XDP_MODE_SKB  = 2,
} PfsXdpMode;

static inline const char* pfs_xdp_mode_str(PfsXdpMode m){
    switch(m){ case PFS_XDP_MODE_DRV: return "DRV"; case PFS_XDP_MODE_SKB: return "SKB"; default: return "AUTO"; }
}

typedef struct {
    struct xsk_socket* xsk;
    PfsXdpUmem* umem;
    struct xsk_ring_cons rx;
    struct xsk_ring_prod tx;
    uint32_t outstanding_tx;
    int ifindex;
    uint32_t queue_id;
    PfsXdpMode mode;        // chosen XDP mode after creation
    int zerocopy_active;    // 1 if zerocopy is active, else 0
} PfsXdpSocket;

int pfs_xdp_umem_create(PfsXdpUmem* u, size_t size, uint32_t frame_size, uint32_t frame_count);
void pfs_xdp_umem_destroy(PfsXdpUmem* u);
int pfs_xdp_socket_create(PfsXdpSocket* s, PfsXdpUmem* u, const char* ifname, uint32_t queue_id, int rx, int tx, int zerocopy, PfsXdpMode mode_req);
void pfs_xdp_socket_destroy(PfsXdpSocket* s);

static inline uint64_t pfs_xdp_frame_addr(PfsXdpUmem* u, uint32_t frame_idx){ return (uint64_t)frame_idx * u->frame_size; }
static inline void* pfs_xdp_frame_ptr(PfsXdpUmem* u, uint64_t addr){ return (uint8_t*)u->buffer + addr; }

#ifdef __cplusplus
}
#endif

