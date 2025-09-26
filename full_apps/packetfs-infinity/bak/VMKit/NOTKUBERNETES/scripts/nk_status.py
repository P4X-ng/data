#!/usr/bin/env python3
"""
NOTKUBERNETES: Show status of running containers across worker VMs.
"""
import json
import subprocess
from pathlib import Path

NK_DIR = Path(__file__).resolve().parents[1]
STATE_FILE = NK_DIR / ".nk/cluster.json"


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def load_state() -> dict:
    if not STATE_FILE.exists():
        raise SystemExit(f"Cluster state not found: {STATE_FILE}. Run nk-up first.")
    return json.loads(STATE_FILE.read_text())


def main():
    state = load_state()
    workers = state["nodes"]["workers"]
    for w in workers:
        ip = w["ip"]
        print(f"\n== {w['name']} ({ip}) ==")
        res = run(["ssh", f"punk@{ip}", "podman", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Ports}}"])
        if res.returncode == 0:
            print(res.stdout.strip() or "(none)")
        else:
            print("Error:", res.stderr.strip())


if __name__ == "__main__":
    main()

