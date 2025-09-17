# pfs_ringpeek (read-only NIC MMIO window)

- Purpose: expose a small, read-only window of a NIC BAR to userspace for diagnostics and ring inspection without touching device state.
- Device: /dev/pfs_ringpeek
- IOCTLs: see realsrc/packetfs/uapi/pfs_ringpeek.h

Build:
- make CC=x86_64-linux-gnu-gcc-13

Usage example:
- echo '{"bar":0,"offset":224,"length":256}' | jq -r > /proc/self/fd/3 # illustrative only; use ioctl from a small userspace helper.