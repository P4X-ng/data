#!/usr/bin/env bash
set -euo pipefail
# pfsctl.sh — Small CLI to wrap common PacketFS workflows
#
# Subcommands:
#   mount-remote   Mount a remote IPROG directory locally via sshfs and expose a local PacketFS view
#   unmount        Unmount a previously mounted PacketFS view and/or sshfs mirror
#   send-dir       Translate a source directory to IPROG locally and rsync IPROGs to a remote host/path
#   scan           Safe TCP reachability scan for a user-provided CIDR/host list and port
#
# Conventions:
# - Prefers Podman over Docker (not used here; future containerization can wrap these flows)
# - Uses central venv at /home/punk/.venv if PacketFS entry points are available there
# - Avoids secrets in plaintext; relies on existing SSH auth
#
# Examples:
#   scripts/pfsctl/pfsctl.sh mount-remote \
#     --host punk@remote --remote-iprog /var/lib/packetfs/iprog \
#     --mnt ./pfs.remote --blob-name pfs_vblob --blob-size 1073741824 --blob-seed 1337 \
#     --meta ./pfsmeta_remote
#
#   scripts/pfsctl/pfsctl.sh send-dir \
#     --src ./data --out-iprog ./iprog \
#     --host punk@remote --remote-iprog /var/lib/packetfs/iprog
#
#   scripts/pfsctl/pfsctl.sh scan --cidr 192.168.1.0/24 --port 8088 --timeout-ms 200

VENV="/home/punk/.venv"
PFS_MOUNT_BIN="$VENV/bin/pfsfs-mount"
PFS_MOUNT_MOD="packetfs.filesystem.pfsfs_mount"
PFS_TRANS_DAEMON="$VENV/bin/pfs-translate-daemon"
PFS_TRANS_MOD="packetfs.tools.translate_daemon"

usage() {
  cat <<'USAGE'
pfsctl — PacketFS helper CLI

Subcommands:
  mount-remote   Mount remote IPROG via sshfs and expose local PacketFS view
  unmount        Unmount a PacketFS view and/or sshfs mirror
  send-dir       Translate a source directory to IPROG and rsync IPROGs to remote
  scan           Safe TCP reachability scan for a CIDR/host list and port

Run 'pfsctl <subcommand> --help' for details.
USAGE
}

need_bin(){ command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }

mount_remote() {
  # Defaults
  local host="" remote_iprog="" mnt="./pfs.remote" meta="./pfsmeta_remote" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337"
  local mirror=".pfs/iprog_remote"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --host) host="$2"; shift 2;;
      --remote-iprog) remote_iprog="$2"; shift 2;;
      --mnt) mnt="$2"; shift 2;;
      --meta) meta="$2"; shift 2;;
      --blob-name) blob_name="$2"; shift 2;;
      --blob-size) blob_size="$2"; shift 2;;
      --blob-seed) blob_seed="$2"; shift 2;;
      --mirror) mirror="$2"; shift 2;;
      -h|--help)
        cat <<'H'
Usage: pfsctl mount-remote --host user@host --remote-iprog DIR [--mnt MNT] [--meta DIR]
                           [--blob-name NAME] [--blob-size BYTES] [--blob-seed SEED]
                           [--mirror LOCAL_DIR]

Steps:
  1) sshfs mount remote IPROG dir at LOCAL mirror (default: .pfs/iprog_remote)
  2) run PacketFS mount locally (read-only) using that mirror as iprog_dir
H
        return 0;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done

  [[ -n "$host" && -n "$remote_iprog" ]] || { echo "--host and --remote-iprog are required" >&2; return 2; }

  need_bin sshfs; need_bin fusermount || true; need_bin stat; need_bin grep
  mkdir -p "$(dirname "$mirror")" "$mirror" "$mnt" "$meta"

  # 1) sshfs mirror
  if mountpoint -q "$mirror"; then
    echo "[pfsctl] mirror already mounted: $mirror"
  else
    echo "[pfsctl] mounting sshfs $host:$remote_iprog -> $mirror"
    sshfs -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3 "$host:$remote_iprog" "$mirror"
  fi

  # 2) Local PacketFS mount (read-only; foreground not needed if tool supports daemonizing)
  echo "[pfsctl] mounting PacketFS at $mnt (iprog_dir=$mirror)"
  if [[ -x "$PFS_MOUNT_BIN" ]]; then
    nohup "$PFS_MOUNT_BIN" --iprog-dir "$mirror" --mount "$mnt" \
      --blob-name "$blob_name" --blob-size "$blob_size" --blob-seed "$blob_seed" \
      --meta-dir "$meta" --window 65536 --read-only --foreground \
      > "$meta/pfsfs_mount.log" 2>&1 & disown || true
  else
    nohup "$VENV/bin/python" -m "$PFS_MOUNT_MOD" --iprog-dir "$mirror" --mount "$mnt" \
      --blob-name "$blob_name" --blob-size "$blob_size" --blob-seed "$blob_seed" \
      --meta-dir "$meta" --window 65536 --read-only --foreground \
      > "$meta/pfsfs_mount.log" 2>&1 & disown || true
  fi
  echo "[pfsctl] launched pfsfs mount; log: $meta/pfsfs_mount.log"
}

unmount_it(){
  local mnt="" mirror=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mnt) mnt="$2"; shift 2;;
      --mirror) mirror="$2"; shift 2;;
      -h|--help)
        echo "Usage: pfsctl unmount [--mnt PATH] [--mirror PATH]"; return 0;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  if [[ -n "$mnt" ]]; then
    echo "[pfsctl] unmounting PacketFS: $mnt"; fusermount -u "$mnt" 2>/dev/null || umount "$mnt" 2>/dev/null || true
  fi
  if [[ -n "$mirror" ]]; then
    echo "[pfsctl] unmounting sshfs mirror: $mirror"; fusermount -u "$mirror" 2>/dev/null || umount "$mirror" 2>/dev/null || true
  fi
}

send_dir(){
  local src="" out_iprog="./iprog" host="" remote_iprog="" blob_name="pfs_vblob" blob_size="1073741824" blob_seed="1337" window="65536"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --src) src="$2"; shift 2;;
      --out-iprog) out_iprog="$2"; shift 2;;
      --host) host="$2"; shift 2;;
      --remote-iprog) remote_iprog="$2"; shift 2;;
      --blob-name) blob_name="$2"; shift 2;;
      --blob-size) blob_size="$2"; shift 2;;
      --blob-seed) blob_seed="$2"; shift 2;;
      --window) window="$2"; shift 2;;
      -h|--help)
        cat <<'H'
Usage: pfsctl send-dir --src DIR --out-iprog DIR --host user@host --remote-iprog DIR [opts]
Steps:
  1) Translate locally (watch once) into out_iprog
  2) rsync out_iprog/*.iprog.json to remote_iprog
H
        return 0;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  [[ -n "$src" && -n "$host" && -n "$remote_iprog" ]] || { echo "--src, --host, --remote-iprog required" >&2; return 2; }
  need_bin rsync
  mkdir -p "$out_iprog"
  echo "[pfsctl] translating $src -> $out_iprog"
  if [[ -x "$PFS_TRANS_DAEMON" ]]; then
    # One-shot translate: run daemon in batch mode if supported; else invoke Python module once
    "$VENV/bin/python" - <<PY
import sys, os
from packetfs.tools.translate_daemon import translate_once
translate_once(src_dir=os.path.abspath("$src"), out_dir=os.path.abspath("$out_iprog"), blob_name="$blob_name", blob_size=int("$blob_size"), blob_seed=int("$blob_seed"), window=int("$window"))
PY
  else
    "$VENV/bin/python" - <<PY
import sys, os
from packetfs.tools.translate_daemon import translate_once
translate_once(src_dir=os.path.abspath("$src"), out_dir=os.path.abspath("$out_iprog"), blob_name="$blob_name", blob_size=int("$blob_size"), blob_seed=int("$blob_seed"), window=int("$window"))
PY
  fi
  echo "[pfsctl] rsync IPROGs to $host:$remote_iprog"
  rsync -av --include "*.iprog.json" --exclude "*" "$out_iprog/" "$host:$remote_iprog/"
}

scan_safe(){
  local cidr="" port=8088 timeout_ms=200 workers=256
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --cidr) cidr="$2"; shift 2;;
      --port) port="$2"; shift 2;;
      --timeout-ms) timeout_ms="$2"; shift 2;;
      --workers) workers="$2"; shift 2;;
      -h|--help)
        cat <<'H'
Usage: pfsctl scan --cidr A.B.C.D/NN [--port N] [--timeout-ms MS] [--workers N]
Notes:
  - Safe reachability check. Sends a single TCP connect probe. Use only on networks you own or have permission to scan.
H
        return 0;;
      *) echo "Unknown arg: $1" >&2; return 2;;
    esac
  done
  [[ -n "$cidr" ]] || { echo "--cidr required" >&2; return 2; }
  need_bin nmap || true; need_bin timeout; need_bin nc
  # Expand CIDR (basic /24 or /16). For generality, rely on nmap -sL to list IPs without scanning.
  mapfile -t hosts < <(nmap -n -sL "$cidr" 2>/dev/null | awk '/Nmap scan report/{print $NF}' | sed 's/[()]//g')
  echo "[pfsctl] scanning ${#hosts[@]} hosts on port $port"
  (
    for h in "${hosts[@]}"; do
      echo "$h"
    done
  ) | xargs -I{} -P "$workers" bash -lc "timeout $((timeout_ms/1000)).$((timeout_ms%1000)) nc -z -w 1 {} $port >/dev/null 2>&1 && echo {}"
}

main(){
  local sub="${1:-}"; shift || true
  case "$sub" in
    mount-remote) mount_remote "$@" ;;
    unmount)      unmount_it "$@" ;;
    send-dir)     send_dir "$@" ;;
    scan)         scan_safe "$@" ;;
    -h|--help|"") usage; exit 0 ;;
    *) echo "Unknown subcommand: $sub" >&2; usage; exit 2 ;;
  esac
}

main "$@"
