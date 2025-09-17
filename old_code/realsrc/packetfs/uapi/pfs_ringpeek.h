/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
#ifndef PFS_RINGPEEK_UAPI_H
#define PFS_RINGPEEK_UAPI_H

#include <linux/types.h>
#include <linux/ioctl.h>

/* Device node: /dev/pfs_ringpeek0 (miscdevice) */
/* Ioctls for configuring the MMIO read window and getting info */

struct pfs_ringpeek_window {
    __u32 bar;         /* BAR index (0..5) */
    __u64 offset;      /* Offset within BAR */
    __u32 length;      /* Window length in bytes (capped by module) */
    __u32 _pad;
};

struct pfs_ringpeek_info {
    __u16 vendor;      /* PCI vendor ID */
    __u16 device;      /* PCI device ID */
    __u32 domain;      /* PCI domain */
    __u8  bus;         /* PCI bus */
    __u8  slot;        /* PCI slot */
    __u8  func;        /* PCI function */
    __u8  _pad;
    __u64 bar_size;    /* Size of selected BAR */
};

#define PFS_RINGPEEK_IOC_MAGIC  0xF7 /* arbitrary */
#define PFS_RINGPEEK_IOC_SET_WINDOW  _IOW(PFS_RINGPEEK_IOC_MAGIC, 1, struct pfs_ringpeek_window)
#define PFS_RINGPEEK_IOC_GET_INFO    _IOR(PFS_RINGPEEK_IOC_MAGIC, 2, struct pfs_ringpeek_info)

#endif /* PFS_RINGPEEK_UAPI_H */