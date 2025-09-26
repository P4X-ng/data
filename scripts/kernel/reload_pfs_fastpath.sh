#!/usr/bin/env bash
set -euo pipefail

# Build and (optionally sign) pfs_fastpath.ko for the running kernel, reload it,
# ensure /dev/pfs_fastpath exists, and show brief diagnostics.

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$here/../.." && pwd)
moddir="$root/src/dev/kernel/pfs_fastpath"
krel=$(uname -r)
hdr="/lib/modules/$krel/build"
mod="$moddir/pfs_fastpath.ko"

log() { printf "[reload] %s\n" "$*"; }

if [[ ! -d "$hdr" ]]; then
  echo "Kernel headers not found: $hdr" >&2
  exit 1
fi

log "Building module for $krel"
make -C "$hdr" M="$moddir" clean >/dev/null 2>&1 || true
make -C "$hdr" M="$moddir" modules

log "Module info:"
modinfo "$mod" | egrep -i "(filename|vermagic|name|depends)" || true

# If kernel enforces signatures and PhoenixGuard is available, sign the module
sig_enforce_file=/proc/sys/kernel/module_sig_enforce
if [[ -r "$sig_enforce_file" ]]; then
  enforce=$(cat "$sig_enforce_file" || echo 0)
else
  enforce=0
fi
pg_modsign="$root/../PhoenixGuard/utils/pgmodsign.py"
pg_cert_dir="$root/../PhoenixGuard/secureboot_certs"
if [[ "$enforce" == "1" ]]; then
  if [[ -x "$pg_modsign" ]]; then
    log "Kernel enforces signatures; signing module via PhoenixGuard"
    # pgmodsign.py expects to modify the file in-place; use --force
    "$pg_modsign" --cert-dir "$pg_cert_dir" --verbose --force "$mod"
    log "Signed module info:"
    modinfo "$mod" | egrep -i "(sig_|signer)" || true
  else
    log "Signature enforcement is ON but PhoenixGuard signer not found: $pg_modsign"
    log "Proceeding without signing may fail."
  fi
fi

# Reload module
if lsmod | grep -qw pfs_fastpath; then
  log "Removing existing pfs_fastpath"
  rmmod pfs_fastpath || true
fi
log "Inserting $mod"
insmod "$mod"
lsmod | grep -w pfs_fastpath || { echo "Failed to load pfs_fastpath" >&2; exit 1; }

# Ensure device node exists
if [[ ! -e /dev/pfs_fastpath ]]; then
  major=$(awk '/pfs_fastpath/ {print $1}' /proc/devices || true)
  if [[ -n "${major:-}" ]]; then
    log "Creating /dev/pfs_fastpath (major $major)"
    mknod /dev/pfs_fastpath c "$major" 0 || true
    chmod 666 /dev/pfs_fastpath || true
  fi
fi
ls -l /dev/pfs_fastpath || true

# Kernel ring diagnostics
log "Recent kernel messages (pfs_fastpath):"
dmesg | tail -n 200 | sed -n 's/.*pfs_fastpath.*/&/p' | tail -n 20 || true

log "Done."