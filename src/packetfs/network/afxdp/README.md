# PacketFS AF_XDP (production)

This directory contains the production AF_XDP stack for PacketFS:
- bpf/: Minimal XDP program that redirects to xsks_map (per RX queue).
- loader/: Standalone XDP loader (attach/detach/status), optional xsks_map pinning.
- user/: (future) shared library and CLIs that wrap libxdp/xsk for RX/TX.

Quick build
- BPF object + skeleton:
  make -C realsrc/packetfs/network/afxdp/bpf
- Loader:
  make -C realsrc/packetfs/network/afxdp/loader

Attach
- Attach in driver/native mode (fallbacks to skb if not supported):
  sudo realsrc/packetfs/network/afxdp/loader/build/pfs_xdp_loader attach \
    --iface enp130s0 \
    --mode drv \
    --obj realsrc/packetfs/network/afxdp/bpf/build/pfs_kern.bpf.o \
    --prog xdp_redirect_xsk \
    --pin /sys/fs/bpf/packetfs

Detach / status
- sudo realsrc/packetfs/network/afxdp/loader/build/pfs_xdp_loader status --iface enp130s0
- sudo realsrc/packetfs/network/afxdp/loader/build/pfs_xdp_loader detach --iface enp130s0

Notes
- Zero-copy expectation: bind_flags should prefer XDP_ZEROCOPY; if your NIC/driver does not support native XDP, the system falls back to generic/SKB (copy).
- The existing AF_XDP TX/RX CLIs live at dev/wip/native/pfs_stream_afxdp_{tx,rx} and will be replaced by production user/ CLIs and libpfs_afxdp.so.
- pCPU optimization: RX can apply PacketFS pCPU ops against spans in the hugepage blob; see realsrc/packetfs/network/pfs_stream_afxdp_rx.c.

