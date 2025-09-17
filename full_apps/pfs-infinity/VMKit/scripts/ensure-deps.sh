#!/usr/bin/env bash
# Install Quickemu and dependencies (idempotent). Defaults to dry-run unless INSTALL=1
set -euo pipefail

INSTALL=${INSTALL:-0}
OS=$(uname -s)
DISTRO="unknown"
PKG=""

if [ -f /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release || true
  DISTRO=${ID:-unknown}
fi

echo "VMKit Setup"
echo "============"

if command -v quickemu >/dev/null 2>&1 && command -v quickget >/dev/null 2>&1; then
  echo "Quickemu and quickget already installed."
  exit 0
fi

if [ "$OS" = "Darwin" ]; then
  echo "Detected macOS (Homebrew)"
  echo "Would run: brew install quickemu qemu"
  if [ "$INSTALL" = "1" ]; then
    brew install quickemu qemu
  else
    echo "Set INSTALL=1 to install."
  fi
  exit 0
fi

if [ "$OS" = "Linux" ]; then
  case "$DISTRO" in
    ubuntu|debian)
      echo "Detected Debian/Ubuntu"
      echo "Would run: sudo apt update && sudo apt -y install quickemu qemu-system qemu-utils ovmf virt-viewer spice-vdagent zsync"
      if [ "$INSTALL" = "1" ]; then
        sudo apt update
        sudo apt -y install quickemu qemu-system qemu-utils ovmf virt-viewer spice-vdagent zsync
      else
        echo "Set INSTALL=1 to install."
      fi
      ;;
    fedora)
      echo "Detected Fedora"
      echo "Would run: sudo dnf -y install quickemu qemu-kvm edk2-ovmf virt-viewer spice-vdagent zsync"
      if [ "$INSTALL" = "1" ]; then
        sudo dnf -y install quickemu qemu-kvm edk2-ovmf virt-viewer spice-vdagent zsync
      else
        echo "Set INSTALL=1 to install."
      fi
      ;;
    arch|archlinux)
      echo "Detected Arch Linux"
      echo "Would run: sudo pacman -S --needed quickemu qemu-full edk2-ovmf virt-viewer spice-vdagent zsync"
      if [ "$INSTALL" = "1" ]; then
        sudo pacman -S --needed quickemu qemu-full edk2-ovmf virt-viewer spice-vdagent zsync
      else
        echo "Set INSTALL=1 to install."
      fi
      ;;
    *)
      echo "Unsupported Linux distro ($DISTRO). Please install quickemu/qemu manually."
      exit 1
      ;;
  esac

  # Group membership guidance
  if ! id -nG "$USER" | grep -qE '\b(kvm|libvirt)\b'; then
    echo "Note: Add yourself to kvm/libvirt groups and re-login:"
    echo "  sudo usermod -aG kvm,libvirt $USER && newgrp kvm"
  fi
  exit 0
fi

echo "Unsupported OS: $OS"
exit 1
