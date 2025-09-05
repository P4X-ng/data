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

typedef struct {
    struct xsk_socket* xsk;
    PfsXdpUmem* umem;
    struct xsk_ring_cons rx;
    struct xsk_ring_prod tx;
    uint32_t outstanding_tx;
    int ifindex;
    uint32_t queue_id;
} PfsXdpSocket;

int pfs_xdp_umem_create(PfsXdpUmem* u, size_t size, uint32_t frame_size, uint32_t frame_count);
void pfs_xdp_umem_destroy(PfsXdpUmem* u);
int pfs_xdp_socket_create(PfsXdpSocket* s, PfsXdpUmem* u, const char* ifname, uint32_t queue_id, int rx, int tx, int zerocopy);
void pfs_xdp_socket_destroy(PfsXdpSocket* s);

static inline uint64_t pfs_xdp_frame_addr(PfsXdpUmem* u, uint32_t frame_idx){ return (uint64_t)frame_idx * u->frame_size; }
static inline void* pfs_xdp_frame_ptr(PfsXdpUmem* u, uint64_t addr){ return (uint8_t*)u->buffer + addr; }

#ifdef __cplusplus
}
#endif

