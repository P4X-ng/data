# Troubleshooting

- /dev/kvm missing
  - Enable hardware virtualization (Intel VT-x/AMD-V) in BIOS/UEFI.
  - Install KVM modules and add your user to kvm/libvirt groups.

- quickemu/quickget not found
  - Run: just setup INSTALL=1

- No display when launching a desktop VM
  - Ensure SPICE client installed (virt-viewer/spice-vdagent).
  - Or run headless: just up NAME HEADLESS=1 and connect via SSH if forwarded.

- Low disk space
  - Keep at least 15 GiB free in vms/ and downloads/.
