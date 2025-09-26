#!/usr/bin/env bash
set -euo pipefail
# run.sh — Boot an OSv image via qemu and forward CLI args to guest
# This script expects /opt/osv/osv.img
# All remaining args are appended to the kernel/cmdline (OSv consumes them).

IMG=${IMG:-/opt/osv/osv.img}
RAM_MB=${RAM_MB:-256}
CPUS=${CPUS:-1}
NETDEV=${NETDEV:-user}   # or tap,bridge if you wire it
EXTRA_QEMU_ARGS=${EXTRA_QEMU_ARGS:-}

if [[ ! -f "$IMG" ]]; then
  echo "OSv image not found at $IMG" >&2
  exit 1
fi

QEMU=qemu-system-x86_64
KVM_ARGS=()
if [[ -e /dev/kvm ]]; then
  KVM_ARGS=( -enable-kvm -cpu host )
else
  KVM_ARGS=( -accel tcg -cpu max )
fi

# OSv-friendly defaults
# -nographic  : serial on stdio
# -device virtio-net-pci : virtio networking
# -drive file=... : OSv image
# -append "args" : pass scanner arguments into OSv userland entrypoint

exec "$QEMU" \
  "${KVM_ARGS[@]}" \
  -m "$RAM_MB" -smp "$CPUS" \
  -nographic \
  -netdev "${NETDEV},id=n0" -device virtio-net-pci,netdev=n0 \
  -drive file="$IMG",if=virtio,format=raw,cache=none,discard=unmap \
  -no-reboot \
  -append "$*" \
  ${EXTRA_QEMU_ARGS}
