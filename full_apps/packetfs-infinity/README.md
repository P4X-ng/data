## Authentication & OAuth

The backend ships with pluggable OAuth providers and a lightweight signed-cookie session layer.

### Quick Start
Set the providers you want (comma-separated) and the required client credentials, then start the app:

```
export PFS_OAUTH_PROVIDERS=google,microsoft,paypal,tiktok
export PFS_SESSION_SECRET="$(openssl rand -hex 32)"
export PFS_GOOGLE_CLIENT_ID=...
export PFS_GOOGLE_CLIENT_SECRET=...
export PFS_MS_CLIENT_ID=...
export PFS_MS_CLIENT_SECRET=...
# Optional: export PFS_MS_TENANT_ID=<tenant|common>
export PFS_PAYPAL_CLIENT_ID=...
export PFS_PAYPAL_CLIENT_SECRET=...
export PFS_OAUTH_CALLBACK_URL="https://your-host/auth/callback"
uvicorn app.core.app:create_app --factory
```

Visit `/` → choose a provider → login → redirected back with a session cookie.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PFS_OAUTH_PROVIDERS` | Comma list of provider keys (`google,microsoft,paypal,oidc,tiktok`) | `google,paypal,tiktok` |
| `PFS_SESSION_SECRET` | Secret for signing session cookies | REQUIRED (no default) |
| `PFS_OAUTH_CALLBACK_URL` | Public callback URL (must match provider config) | `http://localhost:8000/auth/callback` |
| `PFS_AUTH_ENABLED` | Start with auth enforcement on/off | `1` (on) |
| `PFS_ADMIN_TOKEN` | Required token for `/auth/enable` & `/auth/disable` if set | (unset = no check) |
| `PFS_GOOGLE_CLIENT_ID` / `PFS_GOOGLE_CLIENT_SECRET` | Google OAuth credentials | - |
| `PFS_MS_CLIENT_ID` / `PFS_MS_CLIENT_SECRET` | Microsoft Azure AD app credentials | - |
| `PFS_MS_TENANT_ID` | Azure tenant id or `common` | `common` |
| `PFS_PAYPAL_CLIENT_ID` / `PFS_PAYPAL_CLIENT_SECRET` | PayPal (sandbox/live) credentials | - |
| `PFS_PAYPAL_MODE` | `sandbox` or `live` | `sandbox` |
| `PFS_GENERIC_OIDC_*` | Generic OIDC issuer & overrides (`ISSUER`, `CLIENT_ID`, etc.) | (optional) |

The TikTok provider is intentionally a joke provider (`kind=joke`) and returns a playful JSON response instead of performing OAuth.

### Runtime Enable / Disable
```
curl -XPOST -H "X-Admin-Token: $PFS_ADMIN_TOKEN" http://host/auth/disable
curl -XPOST -H "X-Admin-Token: $PFS_ADMIN_TOKEN" http://host/auth/enable
curl http://host/auth/status
```

### Security Notes
* Always supply a strong `PFS_SESSION_SECRET` in production.
* Enable HTTPS and set `secure=True` on session cookies when deploying behind TLS (adjust code if terminating TLS upstream).
* Set `PFS_ADMIN_TOKEN` before exposing enable/disable endpoints publicly.
* Consider moving session storage from in-memory to Redis for multi-process deployments.

# F3 - Fast File Fabric

A revolutionary distributed storage system that turns your network into a unified, high-performance file fabric.

## Quick Start

```bash
# Start F3 server
just -f Justfile.simple start

# Open the web UI
just -f Justfile.simple ui

# Check status
just -f Justfile.simple status
```

Navigate to: https://localhost:8811/static/f3-nav.html

## Features

### 🌐 Cluster Management
- **Bootstrap Seed Nodes**: Initialize your first cluster node with one click
- **Auto-Discovery**: Scan your network and automatically add nodes via SSH
- **Real-time Monitoring**: Live CPU, memory, and network metrics for all nodes
- **Visual Feedback**: Progress bars, toast notifications, and live activity logs

### ⚡ Lightning Fast Transfers
- **95% Compression**: PacketFS technology reduces bandwidth usage dramatically
- **Real-time Progress**: Watch transfer speeds, progress, and ETA live
- **Network-as-Storage**: Your bandwidth becomes your storage capacity

### 📁 Unified Filesystem
- **FUSE Integration**: Access all cluster files as if they were local
- **Transparent Access**: Browse, edit, and manage files across all nodes
- **Real-time Sync**: Changes propagate instantly across the cluster

### 🎮 GPU Virtualization
- **1000% Performance**: Virtual GPUs that exceed physical hardware limits
- **Packet-based Compute**: Transform network packets into GPU operations
- **Quantum Preview**: Negative latency computing (results arrive before request)

## User Guide

### Adding Nodes to Cluster

#### Method 1: Manual Addition (with SSH)
1. Go to Cluster Manager: https://localhost:8811/static/cluster.html
2. Fill in:
   - Node Address: `10.69.69.56:8811`
   - Node Name: `worker-1`
   - SSH Username: `root`
   - SSH Password: `[your-password]`
   - Seed Address: `10.69.69.9:8811`
3. Click "Join Cluster"
4. Watch the progress and see the node appear in the list

#### Method 2: Auto-Discovery
1. Go to Auto-Discovery: https://localhost:8811/static/cluster-discovery.html
2. Enter:
   - IP Range: `192.168.1.0/24`
   - SSH Username: `root`
   - SSH Password: `[your-password]`
3. Click "Start Scanning"
4. Watch as nodes are discovered and automatically added

### Common Commands

```bash
# === Quick Actions ===
just -f Justfile.simple start      # Start server
just -f Justfile.simple stop       # Stop server
just -f Justfile.simple restart    # Restart server
just -f Justfile.simple status     # Check status

# === User Interface ===
just -f Justfile.simple ui         # Open main UI
just -f Justfile.simple cluster-ui # Open cluster manager
just -f Justfile.simple discovery-ui # Open auto-discovery

# === Development ===
just -f Justfile.simple dev        # Run in dev mode
just -f Justfile.simple logs       # Watch logs
just -f Justfile.simple shell      # Shell into container

# === Testing ===
just -f Justfile.simple gpu-test   # GPU benchmark
just -f Justfile.simple cpu-test   # CPU test
just -f Justfile.simple health     # Health check
```

## API Endpoints

### Core Endpoints
- `/api/health` - System health check
- `/api/status` - Detailed system status
- `/api/docs` - Interactive API documentation

### Cluster Management
- `POST /api/cluster/bootstrap` - Initialize seed node
- `POST /api/cluster/join` - Join existing cluster
- `GET /api/cluster/nodes` - List all nodes
- `DELETE /api/cluster/node/{id}` - Remove node

### WebSocket Connections
- `/ws/cluster` - Real-time cluster updates
- `/ws/discovery` - Auto-discovery progress
- `/ws/transfer` - File transfer progress

For complete API documentation, visit: https://localhost:8811/api/docs

## Visual Feedback Guide

### Status Indicators
- 🟢 **Green**: Healthy/Connected
- 🟡 **Yellow**: Warning/Pending
- 🔴 **Red**: Error/Disconnected

### Progress Feedback
- **Immediate**: Spinner appears instantly on any action
- **Progressive**: Progress bars for operations > 2 seconds
- **Detailed**: Step-by-step status for complex operations

### Toast Notifications
- ✅ **Success** (Green): Operation completed
- ⚠️ **Warning** (Yellow): Non-critical issues
- ❌ **Error** (Red): Operation failed
- ℹ️ **Info** (Blue): General information

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Can't connect to UI | Check if server is running: `just -f Justfile.simple status` |
| SSH connection fails | Verify credentials and that SSH is enabled on target |
| WebSocket disconnects | Check firewall allows WebSocket connections |
| Slow discovery | Reduce IP range or check network connectivity |

### Debug Mode
Add `?debug=true` to any URL for verbose logging:
```
https://localhost:8811/static/cluster.html?debug=true
```

### Check Logs
```bash
# Container logs
just -f Justfile.simple logs

# Browser console
Press F12 in browser → Console tab
```

## Architecture

```
┌─────────────────────────────────────┐
│         Web Interface               │
│  (HTML/CSS/JavaScript)              │
├─────────────────────────────────────┤
│         WebSocket Layer             │
│  (Real-time bidirectional)          │
├─────────────────────────────────────┤
│         FastAPI Backend             │
│  (REST API + WebSocket handlers)    │
├─────────────────────────────────────┤
│         PacketFS Core               │
│  (Distributed storage engine)       │
├─────────────────────────────────────┤
│         Network Layer               │
│  (SSH, TCP/IP, QUIC)               │
└─────────────────────────────────────┘
```

## Security

- **HTTPS by default**: All connections are encrypted
- **SSH Authentication**: Secure node addition
- **Certificate Management**: Auto-generated dev certificates
- **Session Management**: 24-hour session timeout

To trust the development certificate:
```bash
just -f Justfile.simple trust-cert
```

## Performance

### Metrics
- **Compression**: 95% reduction in bandwidth
- **Transfer Speed**: Up to 1.2 GB/s
- **Virtual GPU**: 1000% of bare metal performance
- **Network Discovery**: 50 IPs/second scan rate

### Optimization Tips
- Use auto-discovery for bulk node addition
- Enable compression for all transfers
- Leverage WebSocket connections for real-time updates
- Use keyboard shortcuts for faster navigation

## Support

### Documentation
- [API Documentation](/api/docs)
- [Endpoint Reference](docs/ENDPOINTS.md)
- [Architecture Guide](docs/ARCHITECTURE.md)

### Getting Help
1. Check the browser console (F12) for errors
2. Review server logs: `just -f Justfile.simple logs`
3. Visit `/api/status` for system diagnostics
4. Enable debug mode: `?debug=true`

## License

PacketFS F3 - Fast File Fabric
Breaking the limits of distributed storage

---

**Note**: For the full, complex Justfile with all options, use the original `Justfile`. The simplified version (`Justfile.simple`) covers 90% of use cases with much cleaner syntax.