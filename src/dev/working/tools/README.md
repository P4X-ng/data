# Tools

- pfs_ringpeek_ctl: control /dev/pfs_ringpeek and dump a read-only MMIO window

Examples:
- Build: make
- Dump 256 bytes at BAR0 offset 0xE0 as hex:
  ./pfs_ringpeek_ctl --bar 0 --offset 0xE0 --len 256 --hexdump