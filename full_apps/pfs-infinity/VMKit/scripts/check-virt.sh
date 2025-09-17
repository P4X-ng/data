#!/usr/bin/env bash
# Environment diagnostics for VMKit Quickemu workflows
set -euo pipefail

VMS_DIR=${1:-./vms}
DOWNLOADS_DIR=${2:-./downloads}

red() { printf "\033[31m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
info() { printf "• %s\n" "$*"; }
ok() { green "✓ $*"; }
warn() { yellow "! $*"; }
fail() { red "✗ $*"; }

OS=$(uname -s)
DISTRO="unknown"
if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release || true
  DISTRO=${NAME:-unknown}
fi

echo "VMKit Doctor"
echo "============="
info "OS: $OS (${DISTRO})"

# Virtualization support
CPUFLAGS=$(grep -m1 -E 'flags|Features' /proc/cpuinfo 2>/dev/null || true)
if echo "$CPUFLAGS" | grep -qE '\b(vmx|svm)\b'; then ok "CPU virtualization: supported"; else fail "CPU virtualization flags not found (vmx/svm)"; fi

# /dev/kvm (Linux)
if [ "$OS" = "Linux" ]; then
  if [ -e /dev/kvm ]; then ok "/dev/kvm present"; else fail "/dev/kvm missing (enable KVM in BIOS and install kvm modules)"; fi
  # Group membership
  if id -nG "$USER" | grep -qE '\b(kvm|libvirt)\b'; then ok "User in kvm/libvirt groups"; else warn "User not in kvm/libvirt; you may need: sudo usermod -aG kvm,libvirt $USER"; fi
fi

# Tools
if command -v qemu-system-x86_64 >/dev/null 2>&1; then ok "qemu-system-x86_64 found"; else warn "qemu-system-x86_64 not found"; fi
if command -v quickemu >/dev/null 2>&1; then ok "quickemu found"; else warn "quickemu not found (run: just setup)"; fi
if command -v quickget >/dev/null 2>&1; then ok "quickget found"; else warn "quickget not found (run: just setup)"; fi
if command -v virsh >/dev/null 2>&1; then ok "virsh found"; else warn "virsh not found (libvirt clients)"; fi

# Disk space checks
mkdir -p "$VMS_DIR" "$DOWNLOADS_DIR"
VMS_FREE=$(df -Pk "$VMS_DIR" | awk 'NR==2{print $4}')
DL_FREE=$(df -Pk "$DOWNLOADS_DIR" | awk 'NR==2{print $4}')
# Convert 15 GiB to KB (~15728640)
THRESH=$((15*1024*1024))
[ "$VMS_FREE" -ge "$THRESH" ] && ok "${VMS_DIR}: sufficient free space" || warn "${VMS_DIR}: low free space (<15GiB)"
[ "$DL_FREE" -ge "$THRESH" ] && ok "${DOWNLOADS_DIR}: sufficient free space" || warn "${DOWNLOADS_DIR}: low free space (<15GiB)"

# OVMF presence (for Secure Boot)
if [ -r /usr/share/OVMF/OVMF_CODE_4M.secboot.fd ]; then ok "OVMF (Secure Boot) present"; else warn "OVMF (Secure Boot) not found (sudo apt install ovmf)"; fi

# Exit code
HARD_FAIL=0
if ! command -v quickemu >/dev/null 2>&1; then HARD_FAIL=1; fi
if ! command -v quickget >/dev/null 2>&1; then HARD_FAIL=1; fi
if [ "$OS" = "Linux" ] && [ ! -e /dev/kvm ]; then HARD_FAIL=1; fi

if [ "${SIMULATE:-0}" = "1" ]; then
  warn "SIMULATE=1 set: ignoring hard failures for CI"
  exit 0
fi

exit $HARD_FAIL
