#pragma once
#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

// Mode constants
#define PFS_AFXDP_MODE_AUTO 0
#define PFS_AFXDP_MODE_DRV  1
#define PFS_AFXDP_MODE_SKB  2

// Opaque handle
typedef void* pfs_afxdp_handle;

// Open AF_XDP socket with UMEM
// - ifname: interface name (e.g., "enp130s0")
// - queue: RX/TX queue id
// - frame_size: UMEM frame size (2048 typical)
// - ndescs: ring sizes (power of two recommended)
// - require_zc: 1 -> require XDP_ZEROCOPY (fail if unsupported); 0 -> allow copy fallback
// - mode_req: PFS_AFXDP_MODE_{AUTO,DRV,SKB}
// - busy_poll_ms: >0 to enable SO_PREFER_BUSY_POLL and SO_BUSY_POLL
// Returns handle on success, NULL on failure.
pfs_afxdp_handle pfs_afxdp_open(const char* ifname,
                                uint32_t queue,
                                uint32_t frame_size,
                                uint32_t ndescs,
                                int require_zc,
                                int mode_req,
                                int busy_poll_ms);

// Returns 1 if zerocopy is active, else 0
int pfs_afxdp_is_zerocopy(pfs_afxdp_handle h);

// Returns chosen mode: PFS_AFXDP_MODE_{DRV,SKB}
int pfs_afxdp_mode(pfs_afxdp_handle h);

// Prefill FILL ring with up to count frames (returns number actually filled)
int pfs_afxdp_fill(pfs_afxdp_handle h, uint32_t count);

// Poll socket for events (timeout_ms)
int pfs_afxdp_poll(pfs_afxdp_handle h, int timeout_ms);

// Receive up to max_frames; set *bytes_out to sum of rx->len; returns frames received
int pfs_afxdp_rx_burst(pfs_afxdp_handle h, uint32_t max_frames, uint64_t* bytes_out);

// Transmit frames of size frame_len (synthetic payload); returns frames queued
int pfs_afxdp_tx_burst(pfs_afxdp_handle h, uint32_t frame_len, uint32_t frames);

// Close and free
void pfs_afxdp_close(pfs_afxdp_handle h);

#ifdef __cplusplus
}
#endif

