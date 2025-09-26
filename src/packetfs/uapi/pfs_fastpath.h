/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef PFS_FASTPATH_UAPI_H
#define PFS_FASTPATH_UAPI_H

#include <linux/types.h>
#include <linux/ioctl.h>

/*
 * Minimal UAPI for an mmap-able shared ring exposed by /dev/pfs_fastpath.
 * This is intended for SPSC (single-producer, single-consumer) experiments
 * in user-space. It does NOT perform NIC TX/RX; it only provides a fast
 * shared-memory ring region for prototype data exchange and pCPU workloads.
 */

#define PFS_FP_IOC_MAGIC        0xFA

/* Setup the shared area size (in bytes). Kernel will vmalloc a region
 * and lay out as:
 *   [pfs_fp_ring_hdr][u32 slots[size]][padding..][free slab]
 * Returns 0 on success.
 */
struct pfs_fp_setup {
    __u32 ring_bytes;   /* total bytes to vmalloc/map (header+slots+slab) */
    __u32 flags;        /* reserved */
};

#define PFS_FP_IOC_SETUP  _IOW(PFS_FP_IOC_MAGIC, 1, struct pfs_fp_setup)
#define PFS_FP_IOC_RESET  _IO(PFS_FP_IOC_MAGIC,  2)

/* Header placed at the beginning of the mapped region */
struct pfs_fp_ring_hdr {
    __u32 slots;        /* number of u32 entries in slots[] (power of two) */
    __u32 mask;         /* slots-1 */
    __u32 head;         /* consumer index (u32 modulo slots) */
    __u32 tail;         /* producer index (u32 modulo slots) */
    __u32 frame_size;   /* optional per-record size hint (bytes); 0 if variable */
    __u32 data_offset;  /* byte offset from base to start of data slab */
    __u64 region_bytes; /* total bytes of the mapping */
    __u32 reserved[8];
};

#endif /* PFS_FASTPATH_UAPI_H */