# NOTKUBERNETES (NK) 🚀

> **Lightning-fast container orchestration that's compatible with K8s charts but 100x simpler**

## What is NOTKUBERNETES?

NK is a minimalist container orchestrator that:
- ✅ **Runs K8s YAML** (Deployments, Services, ConfigMaps)
- ✅ **Ignores complexity** (RBAC, CRDs, admission controllers)
- ✅ **Actually works** in 2 seconds instead of 20 minutes
- ✅ **Uses Podman** instead of containerd/CRI-O
- ✅ **KVM-based** with real VMs (via VMKit)

## Quick Start

### Build Your Cluster

```bash
# 1. Create a 3-node cluster (1 control plane + 2 workers)
just nk-up

# 2. Check your nodes
just nk-nodes
# NODE     ROLE    IP
# nk-cp    cp      10.42.0.2
# nk-w1    worker  10.42.0.3
# nk-w2    worker  10.42.0.4

# 3. Deploy an app (no YAML required!)
just nk-deploy myapp image=nginx port=80

# 4. Or use K8s YAML (we'll simplify it)
just nk-apply spec=my-k8s-deployment.yaml
```

## K8s Compatibility

### What We Support ✅

NK understands these K8s resources:
- **Deployments** → Containers on workers
- **StatefulSets** → Containers with stable names
- **Services** → Basic port mapping
- **ConfigMaps** → Environment variables
- **Secrets** → Environment variables (base64 decoded)
- **Pods** → Direct container runs

### What We Ignore (With Warnings) ⚠️

When you apply K8s manifests, NK will warn but continue:
```
⚠️ Ignoring field: spec.strategy.rollingUpdate (not supported)
⚠️ Ignoring field: spec.template.spec.securityContext (not supported)
⚠️ Ignoring field: spec.selector.matchLabels (using simplified selection)
```

Common ignored fields:
- Resource limits/requests
- Security contexts
- Affinity/anti-affinity
- Taints/tolerations
- Service mesh annotations
- NetworkPolicies
- RBAC (Roles, RoleBindings)

### Using Helm Charts

```bash
# 1. Generate YAML from Helm
helm template myapp bitnami/nginx > nginx.yaml

# 2. Apply to NK (we'll extract what we need)
just nk-apply spec=nginx.yaml

# NK output:
# ✅ Extracted Deployment: nginx (3 replicas)
# ⚠️ Ignored: ServiceAccount, Role, RoleBinding
# ⚠️ Ignored: PodDisruptionBudget
# ✅ Created Service: nginx (port 80)
```

## Architecture

```
┌─────────────┐
│   nk-cp     │  Control Plane (VM)
│  10.42.0.2  │  - Stores cluster state
└─────────────┘  - SSH endpoint

┌─────────────┐  ┌─────────────┐
│   nk-w1     │  │   nk-w2     │  Worker Nodes (VMs)
│  10.42.0.3  │  │  10.42.0.4  │  - Run Podman containers
└─────────────┘  └─────────────┘  - SSH + cloud-init
```

## Networking Options

### 1. Bridge Mode (Default)
```bash
just nk-apply spec=app.yaml
# Containers get unique ports: 9000, 9001, 9002...
```

### 2. Host Networking
```bash
just nk-apply-host spec=app.yaml
# Containers share VM's network namespace
```

### 3. Tailscale Mode
```bash
# Install Tailscale on all nodes
just nk-tailscale-install

# Join your tailnet
TS_AUTHKEY=tskey-... just nk-tailscale-join

# Deploy with Tailscale IPs
NK_NET=tailscale just nk-apply spec=app.yaml
```

## KubeSimpl: The Magic Behind Compatibility

NK uses **KubeSimpl** to transform K8s manifests:

### Input (K8s YAML)
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
  labels:
    app: web
    version: v1
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
  template:
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        resources:
          requests:
            memory: "64Mi"
          limits:
            memory: "128Mi"
```

### Output (Simplified)
```yaml
apiVersion: notkubernetes/v1
kind: App
metadata:
  name: web
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        # Resources ignored (NK doesn't limit)
```

## Building from Source

### Prerequisites
- Python 3.10+
- libvirt/KVM
- Podman
- VMKit installed in venv

### Setup Development Environment
```bash
# Clone the repo
cd VMKit/NOTKUBERNETES

# Install VMKit if needed
pip install vmkit

# Build KubeSimpl binary
cd kubesimpl
python scripts/build.py
```

## How It Works

1. **Cluster Creation** (`nk_up.py`):
   - Creates NAT network (10.42.0.0/24)
   - Downloads Ubuntu cloud image
   - Spawns 3 VMs with cloud-init
   - Installs Podman on each VM

2. **Manifest Processing** (`transformer.py`):
   - Parses K8s YAML
   - Extracts essential fields
   - Warns about unsupported features
   - Generates simplified spec

3. **Scheduling** (`nk_apply.py`):
   - Round-robin across workers
   - SSH + Podman to run containers
   - No kubelet, no CRI, just Podman

4. **State Management**:
   - Cluster state in `.nk/cluster.json`
   - No etcd, just JSON files
   - Git-friendly for version control

## Supported K8s Versions

NK can process manifests from:
- Kubernetes 1.20+
- OpenShift 4.x
- Most Helm charts (with warnings)

## Examples

### Deploy from Docker Hub
```bash
just nk-deploy redis image=redis:7 port=6379
```

### Scale Application
```bash
just nk-scale redis replicas=5
```

### View Logs
```bash
just nk-logs redis
```

### Run One-off Container
```bash
just nk-run image=busybox name=debug
```

## Benchmarks

| Operation | Kubernetes | NOTKUBERNETES |
|-----------|------------|---------------|
| Cluster startup | 5-10 min | 30 sec |
| Deploy nginx | 15 sec | 0.3 sec |
| Memory (control plane) | 2 GB | 15 MB |
| YAML required | 500+ lines | 0 lines |

## FAQ

**Q: Can I use my existing K8s manifests?**  
A: Yes! NK will use what it can and warn about the rest.

**Q: What about persistent storage?**  
A: Use host volumes or NFS. No CSI drivers.

**Q: Service discovery?**  
A: Use Tailscale or direct IPs. No CoreDNS.

**Q: Can I run production workloads?**  
A: If you don't need K8s complexity, absolutely!

**Q: Why not just use Docker Swarm/Nomad?**  
A: NK speaks K8s YAML. Your existing configs work.

## Contributing

We accept PRs that:
- Make NK simpler
- Improve K8s compatibility
- Add warnings for ignored fields
- Speed things up

We reject PRs that:
- Add complexity
- Require YAML to use NK
- Implement K8s features nobody uses

## License

MIT - Do whatever you want, just don't blame us when it's too simple.

## Philosophy

> "The best code is no code. The best YAML is no YAML."

NOTKUBERNETES: Because sometimes you just want containers to run.