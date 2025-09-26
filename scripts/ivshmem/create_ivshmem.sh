#!/usr/bin/env bash
set -euo pipefail
# create_ivshmem.sh — create a backing file for ivshmem and print libvirt XML snippet
# Usage:
#   scripts/ivshmem/create_ivshmem.sh --path /dev/shm/pfs_scan_ring.bin --size-mb 64 --name pfs-scan-shm
# Then attach to a VM with the printed <shmem> device XML (virsh attach-device or domain XML edit).

PATH_OUT="/dev/shm/pfs_scan_ring.bin"
SIZE_MB=64
NAME="pfs-scan-shm"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) PATH_OUT="$2"; shift 2;;
    --size-mb) SIZE_MB="$2"; shift 2;;
    --name) NAME="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 --path /dev/shm/file --size-mb 64 --name shm-name"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac

done

SIZE_BYTES=$(( SIZE_MB * 1024 * 1024 ))
truncate -s "$SIZE_BYTES" "$PATH_OUT"
chmod 666 "$PATH_OUT" || true

cat <<XML
<!-- Add this under <devices> in the domain XML -->
<shmem name='${NAME}'>
  <model type='ivshmem-plain'/>
  <size unit='M'>${SIZE_MB}</size>
  <server path='${PATH_OUT}'/>
</shmem>
XML

echo "[ok] ivshmem backing file created: $PATH_OUT (${SIZE_MB} MiB)"