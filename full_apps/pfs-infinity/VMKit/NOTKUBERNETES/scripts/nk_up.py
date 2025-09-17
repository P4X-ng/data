#!/usr/bin/env python3
"""
NOTKUBERNETES: Bring up a minimal custom cluster using VMKit + libvirt/KVM.
- Creates a NAT network (nk-net)
- Downloads Ubuntu cloud image (24.04) into NOTKUBERNETES/images/
- Creates/starts 3 VMs: nk-cp, nk-w1, nk-w2 with Secure Boot
- Installs podman, python, openssh-server via cloud-init packages
- Writes cluster state (IPs) to NOTKUBERNETES/.nk/cluster.json
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

VMKIT = "/home/punk/.venv/bin/vmkit"
REPO_ROOT = Path(__file__).resolve().parents[2]  # .../HGWS
NK_DIR = Path(__file__).resolve().parents[1]      # .../VMKit/NOTKUBERNETES
STATE_DIR = NK_DIR / ".nk"
STATE_FILE = STATE_DIR / "cluster.json"
IMAGES_DIR = NK_DIR / "images"
IMAGE_PATH = IMAGES_DIR / "ubuntu-24.04-cloud.img"
IMAGE_URL = "https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img"
NETWORK_NAME = "nk-net"
SUBNET = "10.42.0.0/24"
VMS = [
    {"name": "nk-cp", "mem": "8G", "cpus": "4"},
    {"name": "nk-w1", "mem": "4G", "cpus": "2"},
    {"name": "nk-w2", "mem": "4G", "cpus": "2"},
]
PACKAGES = "podman,python3-pip,python3-venv,openssh-server"
USERNAME = "punk"


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


def ensure_dirs():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def ensure_network():
    res = run([VMKIT, "network", "create-nat", NETWORK_NAME, "--subnet", SUBNET])
    if res.returncode != 0 and "already exists" not in (res.stderr + res.stdout):
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(f"Failed to create network {NETWORK_NAME}")


def ensure_image():
    if IMAGE_PATH.exists():
        return
    # Prefer wget if present, else curl
    if shutil.which("wget"):
        res = run(["wget", "-O", str(IMAGE_PATH), IMAGE_URL])
    else:
        res = run(["curl", "-L", "-o", str(IMAGE_PATH), IMAGE_URL])
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit("Failed to download Ubuntu cloud image")


def create_vm(name: str, mem: str, cpus: str):
    args = [
        VMKIT,
        "create",
        name,
        str(IMAGE_PATH),
        "--memory", mem,
        "--cpus", cpus,
        "--network", NETWORK_NAME,
        "--username", USERNAME,
        "--packages", PACKAGES,
        "--start",
    ]
    res = run(args)
    # If VM exists, try to start it instead
    if res.returncode != 0 and "already exists" in (res.stderr + res.stdout):
        res2 = run([VMKIT, "start", name])
        if res2.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            print(res2.stdout)
            print(res2.stderr)
            raise SystemExit(f"Failed to start existing VM {name}")
    elif res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit(f"Failed to create VM {name}")


def get_ip_from_virsh(name: str) -> str | None:
    # Try multiple sources
    for source in ("lease", "agent", "arp"):
        res = run(["virsh", "domifaddr", name, "--source", source, "--full"])
        if res.returncode == 0 and res.stdout:
            # Parse IPv4 address like '192.168.x.y/24'
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)/(?:\d+)", res.stdout)
            if m:
                return m.group(1)
    # Fallback: plain domifaddr
    res = run(["virsh", "domifaddr", name])
    if res.returncode == 0 and res.stdout:
        m = re.search(r"(\d+\.\d+\.\d+\.\d+)/(?:\d+)", res.stdout)
        if m:
            return m.group(1)
    return None


def collect_ips() -> dict:
    ips: dict[str, str] = {}
    for vm in VMS:
        name = vm["name"]
        ip = get_ip_from_virsh(name)
        if not ip:
            raise SystemExit(f"Could not determine IP for {name}; ensure guest agent/leases available.")
        ips[name] = ip
    return ips


def write_state(ips: dict):
    state = {
        "network": NETWORK_NAME,
        "subnet": SUBNET,
        "username": USERNAME,
        "nodes": {
            "control_plane": {"name": "nk-cp", "ip": ips["nk-cp"]},
            "workers": [
                {"name": "nk-w1", "ip": ips["nk-w1"]},
                {"name": "nk-w2", "ip": ips["nk-w2"]},
            ],
        },
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def main():
    print("NOTKUBERNETES: bringing up cluster...")
    ensure_dirs()
    ensure_network()
    ensure_image()
    for vm in VMS:
        create_vm(vm["name"], vm["mem"], vm["cpus"])
    ips = collect_ips()
    write_state(ips)
    print("✅ Cluster up")
    print(f"State: {STATE_FILE}")
    print("Nodes:")
    for name, ip in ips.items():
        print(f"  - {name}: {ip}")


if __name__ == "__main__":
    main()

