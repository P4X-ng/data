#!/usr/bin/env python3
"""
NOTKUBERNETES: Apply a simplified spec to the cluster.
- Expands the simplified YAML using KubeSimpl
- Schedules containers across workers (very simple spread)
- Uses SSH to run Podman containers on workers

Usage:
  nk_apply.py <simplified_yaml_path>
"""
import json
import os
import subprocess
import sys
from pathlib import Path

VMKIT_DIR = Path(__file__).resolve().parents[1]
NK_DIR = VMKIT_DIR
STATE_FILE = NK_DIR / ".nk/cluster.json"
KUBESIMPL = NK_DIR / "bin/kubesimpl"

POD_DEFAULT_PORT = 80  # default when not given


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, text=True, capture_output=True)


def load_state() -> dict:
    if not STATE_FILE.exists():
        raise SystemExit(f"Cluster state not found: {STATE_FILE}. Run nk-up first.")
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_spec(simplified: Path, expanded: Path):
    expanded.parent.mkdir(parents=True, exist_ok=True)
    res = run([str(KUBESIMPL), "expand", str(simplified), str(expanded)])
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        raise SystemExit("Failed to expand spec with KubeSimpl")


def pick_workers(state: dict) -> list[dict]:
    return state["nodes"]["workers"]


def _get_tailscale_ip(node_ip: str) -> str | None:
    """Return the tailscale IPv4 of the node if available."""
    res = run(["ssh", f"punk@{node_ip}", "tailscale", "ip", "-4"])  # returns first IP
    if res.returncode == 0 and res.stdout:
        ip = res.stdout.strip().splitlines()[0].strip()
        if ip:
            return ip
    return None


def schedule_and_apply(expanded_path: Path, workers: list[dict]):
    import yaml
    with open(expanded_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)

    name = manifest["metadata"]["name"]
    replicas = manifest.get("spec", {}).get("replicas", 1)

    # Try to read single-container image+ports from template spec
    tmpl = manifest.get("spec", {}).get("template", {})
    spec = tmpl.get("spec", {})
    containers = spec.get("containers", [])
    if not containers:
        raise SystemExit("Expanded manifest has no containers; unsupported in this simple scheduler")

    image = containers[0].get("image", "")
    ports = containers[0].get("ports", [])
    port_list = [p.get("containerPort", POD_DEFAULT_PORT) for p in ports] or [POD_DEFAULT_PORT]

    # Networking mode
    net_env = os.environ.get("NK_NET", "").lower()
    net_mode = "host" if net_env in ("host", "tailscale") else "bridge"
    host_port_base = int(os.environ.get("NK_HOST_PORT_BASE", "9000"))

    # simple round-robin across workers
    for i in range(replicas):
        worker = workers[i % len(workers)]
        ip = worker["ip"]
        instance_name = f"{name}-{i}"
        container_port = port_list[0]

        if net_mode == "host":
            # host networking: share node network, no explicit port publishing
            cmd = [
                "ssh", f"punk@{ip}",
                "podman", "run", "-d", "--replace",
                "--name", instance_name,
                "--label", f"nk.app={name}",
                "--label", f"nk.net={net_env or 'host'}",
                "--network", "host",
                image,
            ]
        else:
            # bridge: publish unique host port for quick access
            host_port = host_port_base + i
            cmd = [
                "ssh", f"punk@{ip}",
                "podman", "run", "-d", "--replace",
                "--name", instance_name,
                "--label", f"nk.app={name}",
                "--label", f"nk.net=bridge",
                "-p", f"{host_port}:{container_port}",
                image,
            ]

        res = run(cmd)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            raise SystemExit(f"Failed to run container on {ip}")

        if net_env == "tailscale":
            ts_ip = _get_tailscale_ip(ip)
            endpoint = f"ts:{ts_ip}:{container_port}" if ts_ip else f"node:{ip}:{container_port}"
            print(f"✅ {instance_name} on {ip} (tailscale) -> {endpoint} -> {image}")
        elif net_mode == "host":
            print(f"✅ {instance_name} on {ip} (host) -> node:{ip}:{container_port} -> {image}")
        else:
            print(f"✅ {instance_name} on {ip} -> host:{host_port_base + i} -> {image}")


def main():
    if len(sys.argv) < 2:
        print("Usage: nk_apply.py <simplified_yaml_path>")
        sys.exit(2)
    simplified = Path(sys.argv[1]).resolve()
    if not simplified.exists():
        raise SystemExit(f"Simplified spec not found: {simplified}")

    state = load_state()
    expanded = NK_DIR / ".nk/expanded.yaml"
    expand_spec(simplified, expanded)

    workers = pick_workers(state)
    schedule_and_apply(expanded, workers)


if __name__ == "__main__":
    main()

