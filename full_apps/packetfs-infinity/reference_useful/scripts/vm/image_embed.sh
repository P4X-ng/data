#!/usr/bin/env bash
set -euo pipefail
# Embed a container image tar into a VM disk and install a systemd unit
# Requirements: libguestfs-tools (guestfish), virtiofs-aware guest (for runtime mounts later)
# Usage:
#   scripts/vm/image_embed.sh --img pfs-infinity.qcow2 --tar .vm/pfs-infinity-image.tar --name packetfs/pfs-infinity:latest --autostart 1
# Behavior:
# - Copies TAR into /var/lib/pfs/ inside the VM image
# - Writes /usr/local/bin/pfs-image-import.sh and systemd unit pfs-image-import.service
# - On first boot, service imports the image into podman and (optionally) autostarts it

IMG=""
TAR=""
NAME=""
AUTOSTART="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --img) IMG=${2:?}; shift 2;;
    --tar) TAR=${2:?}; shift 2;;
    --name) NAME=${2:?}; shift 2;;
    --autostart) AUTOSTART=${2:?}; shift 2;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

if [[ -z "$IMG" || -z "$TAR" || -z "$NAME" ]]; then
  echo "usage: $0 --img VM_DISK --tar IMAGE_TAR --name OCI_NAME [--autostart 0|1]" >&2
  exit 2
fi

if ! command -v guestfish >/dev/null 2>&1; then
  echo "guestfish not found; install libguestfs-tools" >&2
  exit 3
fi

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

IMPORT_SH="$WORK/pfs-image-import.sh"
UNIT="$WORK/pfs-image-import.service"

cat > "$IMPORT_SH" <<'EOSH'
#!/usr/bin/env bash
set -euo pipefail
IMG_TAR="/var/lib/pfs/pfs-infinity-image.tar"
NAME_FILE="/var/lib/pfs/oci_name.txt"
OCI_NAME="$(cat "$NAME_FILE" 2>/dev/null || echo packetfs/pfs-infinity:latest)"
mkdir -p /var/lib/pfs
if [ -f "$IMG_TAR" ]; then
  systemctl start podman || true
  podman load -i "$IMG_TAR" || true
  # Optional autostart label check
  if podman image exists "$OCI_NAME"; then
    if [ -f /etc/pfs/autostart ]; then
      podman run --rm -d --name pfs-infinity --net=host \
        -v /share:/share -v /mnt/huge1G:/mnt/huge1G \
        -e PFS_BLOB_DIR=/mnt/huge1G -e PFS_SHARE_DIR=/share \
        -e REDIS_URL=redis://127.0.0.1:6389/0 \
        "$OCI_NAME" || true
    fi
  fi
fi
EOSH

cat > "$UNIT" <<'EOUNIT'
[Unit]
Description=Import embedded PacketFS container image and optional autostart
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/pfs-image-import.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOUNIT

chmod 0755 "$IMPORT_SH"

# Write files into the VM image using guestfish (assumes / is the first partition)
# We will try to mount common partition layouts; adjust as needed
run_guestfish() {
  guestfish <<GF
add "$IMG"
run
# try common partitions; ignore errors
try : mount-ro /dev/sda1 /
try : mount-ro /dev/vda1 /
# remount rw if possible
umount-all
try : mount /dev/sda1 /
try : mount /dev/vda1 /
mkdir-p /var/lib/pfs
upload "$TAR" /var/lib/pfs/pfs-infinity-image.tar
write /var/lib/pfs/oci_name.txt "$NAME\n"
mkdir-p /etc/pfs
# autostart file
rm-f /etc/pfs/autostart
GF
}

run_guestfish

# Create or remove autostart flag
if [[ "$AUTOSTART" == "1" ]]; then
  guestfish <<GF
add "$IMG"
run
try : mount /dev/sda1 /
try : mount /dev/vda1 /
write /etc/pfs/autostart "1\n"
upload "$IMPORT_SH" /usr/local/bin/pfs-image-import.sh
upload "$UNIT" /etc/systemd/system/pfs-image-import.service
chmod 0755 /usr/local/bin/pfs-image-import.sh
ln-sf /etc/systemd/system/pfs-image-import.service /etc/systemd/system/multi-user.target.wants/pfs-image-import.service
GF
else
  guestfish <<GF
add "$IMG"
run
try : mount /dev/sda1 /
try : mount /dev/vda1 /
rm-f /etc/pfs/autostart
upload "$IMPORT_SH" /usr/local/bin/pfs-image-import.sh
upload "$UNIT" /etc/systemd/system/pfs-image-import.service
chmod 0755 /usr/local/bin/pfs-image-import.sh
# do not enable
GF
fi

echo "[vm-image] Embedded $TAR and installed import service (autostart=$AUTOSTART)"