#!/usr/bin/env python3
"""
NOTKUBERNETES: Destroy cluster VMs and network, clean state.
"""
import json
import subprocess
from pathlib import Path

VMKIT = "/home/punk/.venv/bin/vmkit"
NK_DIR = Path(__file__).resolve().parents[1]
STATE_FILE = NK_DIR / ".nk/cluster.json"


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def destroy_vm(name: str):
    # Stop then destroy; ignore errors
    run([VMKIT, "stop", name])
    run([VMKIT, "destroy", name, "--force"])


def main():
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())
        cp = state["nodes"]["control_plane"]["name"]
        workers = [w["name"] for w in state["nodes"]["workers"]]
        for name in workers + [cp]:
            destroy_vm(name)
        # Network name
        net = state.get("network")
        if net:
            run([VMKIT, "network", "delete-network", net])
        # Clean state
        STATE_FILE.unlink(missing_ok=True)
        print("✅ Cluster destroyed")
    else:
        print("No cluster state; nothing to destroy.")


if __name__ == "__main__":
    main()

