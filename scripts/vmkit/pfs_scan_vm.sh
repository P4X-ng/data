#!/usr/bin/env bash
set -euo pipefail
# pfs_scan_vm.sh — Create a tiny VMKit VM that on first boot installs Podman
# and runs the OSv scanner container from a registry.
#
# Usage:
#   scripts/vmkit/pfs_scan_vm.sh --name pfs-scan --image ~/vm-images/ubuntu-22.04-server-cloudimg-amd64.img \
#     --registry 192.168.122.1:5000 --tag osv-scanner:latest \
#     --memory 512M --cpus 1
#
# The cloud-init config installs podman, pulls REGISTRY/TAG, and runs it with --net=host.

NAME="pfs-scan"
IMAGE=""
REGISTRY="192.168.122.1:5000"
TAG="osv-scanner:latest"
MEMORY="512M"
CPUS="1"
ARGS="--cidr 10.0.0.0/8 --ports 80,443 --rate 200000"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --image) IMAGE="$2"; shift 2;;
    --registry) REGISTRY="$2"; shift 2;;
    --tag) TAG="$2"; shift 2;;
    --memory) MEMORY="$2"; shift 2;;
    --cpus) CPUS="$2"; shift 2;;
    --args) ARGS="$2"; shift 2;;
    -h|--help)
      echo "Usage: $0 --name NAME --image PATH --registry HOST:PORT [--tag T] [--memory 512M] [--cpus 1] [--args '...']"; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

[[ -n "$IMAGE" ]] || { echo "--image required (Ubuntu cloud image)" >&2; exit 2; }

# Cloud-init: install podman; pull and run the OSv scanner container at boot
CLOUDINIT=$(mktemp)
cat > "$CLOUDINIT" <<CLOUD
#cloud-config
package_update: true
packages: [podman]
runcmd:
  - |
    cat >/etc/systemd/system/osv-scan.service <<'UNIT'
    [Unit]
    Description=OSv Scanner
    After=network-online.target
    Wants=network-online.target

    [Service]
    Type=simple
    ExecStart=/usr/bin/podman run --rm --net=host --device /dev/kvm ${REGISTRY}/${TAG} ${ARGS}
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    UNIT
  - systemctl daemon-reload
  - systemctl enable --now osv-scan.service
CLOUD

# Create and start
vmkit create "$NAME" "$IMAGE" --memory "$MEMORY" --cpus "$CPUS" --graphics none --start
# Seed cloud-init (your vmkit may provide a dedicated command; if not, keep instructions here)
if vmkit cloud seed "$NAME" "$CLOUDINIT" 2>/dev/null; then
  echo "[pfs-scan] seeded cloud-init for $NAME"
else
  echo "[pfs-scan] NOTE: please seed cloud-init per your VMKit version; file at: $CLOUDINIT"
fi

echo "[pfs-scan] VM created: $NAME (mem=$MEMORY cpus=$CPUS), registry=$REGISTRY image=${TAG}"
echo "[pfs-scan] console: vmkit console $NAME"
