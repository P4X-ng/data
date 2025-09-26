# F3 PacketFS API Endpoints & User Interface Guide

## Table of Contents
1. [Web Interface URLs](#web-interface-urls)
2. [REST API Endpoints](#rest-api-endpoints)
3. [WebSocket Endpoints](#websocket-endpoints)
4. [User Feedback & Status Codes](#user-feedback--status-codes)
5. [Common User Workflows](#common-user-workflows)

---

## Web Interface URLs

### Main Navigation
| URL | Description | User Experience |
|-----|-------------|-----------------|
| `/` | Landing page | Welcome screen with quick actions |
| `/static/f3-nav.html` | Main navigation hub | Central dashboard with all features |
| `/static/cluster.html` | Cluster management | Real-time node status and control |
| `/static/cluster-discovery.html` | Auto-discovery | Scan networks and add nodes automatically |
| `/static/transfer.html` | File transfer interface | Drag-drop files with progress bars |
| `/static/browse.html` | File browser | Navigate distributed filesystem |
| `/api/docs` | API documentation | Interactive API explorer (Swagger) |

### Cluster Management Pages
| URL | Description | Features |
|-----|-------------|----------|
| `/static/cluster.html#bootstrap` | Bootstrap seed node | Initialize first cluster node |
| `/static/cluster.html#add-node` | Add nodes | Join existing cluster |
| `/static/cluster-discovery.html#scan` | Network scanner | Auto-discover SSH nodes |

---

## REST API Endpoints

### Health & Status
| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/api/health` | GET | System health check | `{"status": "healthy", "timestamp": "..."}` |
| `/api/status` | GET | Detailed system status | Full system metrics |
| `/api/whoami` | GET | Current user/node info | Node identity and capabilities |

### Cluster Management
| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/cluster/bootstrap` | POST | Initialize seed node | `{"name": "seed-1", "bind_address": "0.0.0.0:8811"}` | `{"node_id": "...", "status": "initialized"}` |
| `/api/cluster/join` | POST | Join existing cluster | `{"name": "node-2", "seed_address": "10.69.69.9:8811", "ssh_username": "root", "ssh_password": "..."}` | `{"status": "joined", "cluster_id": "..."}` |
| `/api/cluster/nodes` | GET | List all nodes | - | `[{"id": "...", "name": "...", "status": "..."}]` |
| `/api/cluster/node/{id}` | GET | Get node details | - | Full node information |
| `/api/cluster/node/{id}` | DELETE | Remove node | - | `{"status": "removed"}` |

### File Transfer
| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/transfer/send` | POST | Send file | `{"file": "...", "destination": "node-id"}` | `{"transfer_id": "...", "status": "started"}` |
| `/api/transfer/{id}/status` | GET | Transfer status | - | Progress, speed, ETA |
| `/api/transfer/{id}/cancel` | POST | Cancel transfer | - | `{"status": "cancelled"}` |

### File System
| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|--------------|----------|
| `/api/browse/` | GET | List root directory | - | File/folder listing |
| `/api/browse/{path}` | GET | List directory | - | File/folder listing |
| `/api/file/{path}` | GET | Download file | - | File content |
| `/api/file/{path}` | PUT | Upload file | File content | `{"status": "uploaded"}` |
| `/api/file/{path}` | DELETE | Delete file | - | `{"status": "deleted"}` |

### GPU/Compute
| Endpoint | Method | Description | Response |
|----------|--------|-------------|----------|
| `/api/gpu/status` | GET | GPU status | Current GPU utilization |
| `/api/gpu/benchmark` | POST | Run GPU benchmark | Benchmark results |
| `/api/compute/job` | POST | Submit compute job | Job ID and status |

---

## WebSocket Endpoints

### Real-Time Connections
| Endpoint | Purpose | Message Format | Events |
|----------|---------|----------------|--------|
| `/ws/cluster` | Cluster updates | JSON | `node_added`, `node_removed`, `status_change`, `metric_update` |
| `/ws/transfer` | Transfer progress | JSON | `progress`, `speed_update`, `completed`, `error` |
| `/ws/discovery` | Auto-discovery | JSON | `scan_progress`, `node_found`, `scan_complete` |
| `/ws/logs` | Live logs | JSON | `log_entry`, `error`, `warning`, `info` |

### WebSocket Message Examples

#### Cluster WebSocket
```javascript
// Client -> Server
{
    "action": "subscribe",
    "node_id": "node-1"
}

// Server -> Client
{
    "type": "node_update",
    "node": {
        "id": "node-1",
        "status": "healthy",
        "cpu": 23.5,
        "memory": 45.2
    }
}
```

#### Discovery WebSocket
```javascript
// Client -> Server
{
    "action": "scan",
    "ip_range": "192.168.1.0/24",
    "username": "root",
    "password": "secure123",
    "auto_add": true
}

// Server -> Client
{
    "type": "scan_progress",
    "progress": 50,
    "total": 254,
    "found": 3,
    "current_ip": "192.168.1.127"
}
```

---

## User Feedback & Status Codes

### Visual Feedback Elements
| Element | Purpose | Implementation |
|---------|---------|----------------|
| Toast Notifications | Quick status updates | Success (green), Error (red), Info (blue) |
| Progress Bars | Long operations | Smooth animations with percentage |
| Loading Spinners | Async operations | Rotating indicators during API calls |
| Status Indicators | Node/service health | Green (healthy), Yellow (warning), Red (error) |

### HTTP Status Codes
| Code | Meaning | User Message |
|------|---------|--------------|
| 200 | Success | "Operation completed successfully" |
| 201 | Created | "Resource created successfully" |
| 400 | Bad Request | "Please check your input" |
| 401 | Unauthorized | "Please log in to continue" |
| 403 | Forbidden | "You don't have permission for this action" |
| 404 | Not Found | "Resource not found" |
| 409 | Conflict | "Resource already exists" |
| 500 | Server Error | "Something went wrong, please try again" |

### User Experience Patterns
1. **Immediate Feedback**: Show spinner/loading state immediately on action
2. **Progress Updates**: Real-time progress for operations > 2 seconds
3. **Clear Errors**: Specific, actionable error messages
4. **Success Confirmation**: Toast + visual update on successful operations
5. **Persistent State**: Remember user preferences and last actions

---

## Common User Workflows

### 1. Bootstrap New Cluster
```
1. Navigate to /static/cluster.html
2. Enter seed node name (e.g., "seed-1")
3. Enter bind address (default: 0.0.0.0:8811)
4. Click "Initialize Seed Node"
5. Watch progress bar (20% → 40% → 60% → 80% → 100%)
6. See success toast and node appear in list
```

### 2. Add Node via SSH
```
1. Navigate to /static/cluster.html
2. Fill in:
   - Node Address: 10.69.69.56:8811
   - Node Name: worker-1
   - SSH Username: root
   - SSH Password: [password]
   - Seed Address: 10.69.69.9:8811
3. Click "Join Cluster"
4. Watch connection progress
5. See node added to cluster list
```

### 3. Auto-Discover Network
```
1. Navigate to /static/cluster-discovery.html
2. Enter IP range (e.g., 192.168.1.0/24)
3. Enter SSH credentials
4. Select "Auto-add to cluster" option
5. Click "Start Scanning"
6. Watch scan progress with live stats:
   - IPs Scanned: 127/254
   - SSH Found: 5
   - Authenticated: 3
   - Added to Cluster: 3
7. See discovered nodes with full system info
```

### 4. Transfer Files
```
1. Navigate to /static/transfer.html
2. Drag files to drop zone OR click to browse
3. Select destination node
4. Watch real-time:
   - Transfer speed: 125 MB/s
   - Progress: 45%
   - ETA: 2m 30s
5. See completion notification
```

### 5. Browse Distributed Files
```
1. Navigate to /static/browse.html
2. Click folders to navigate
3. Right-click for context menu:
   - Download
   - Delete
   - Move
   - Properties
4. See file details in sidebar
```

---

## Error Handling Examples

### Network Errors
```javascript
// User sees:
Toast: "Connection lost. Retrying in 3 seconds..."
Status: Yellow warning indicator
Action: Auto-reconnect with exponential backoff
```

### Authentication Errors
```javascript
// User sees:
Toast: "Invalid SSH credentials"
Field: Red border on password field
Help: "Please check your username and password"
```

### Operation Failures
```javascript
// User sees:
Toast: "Failed to add node"
Log: "[ERROR] Connection refused: 10.69.69.56:22"
Action: "Check if SSH is enabled on target machine"
```

---

## Performance Tips

### For Users
1. **Batch Operations**: Add multiple nodes at once using auto-discovery
2. **Quick Actions**: Use keyboard shortcuts (Ctrl+N for new node)
3. **Filters**: Use search/filter to find specific nodes quickly
4. **Presets**: Save common configurations

### For Developers
1. **WebSocket Subscriptions**: Only subscribe to needed events
2. **Pagination**: Use page parameters for large datasets
3. **Caching**: Browser caches static resources automatically
4. **Compression**: All responses are gzip compressed

---

## Security Notes

### Authentication
- All API endpoints require authentication (except /api/health)
- SSH passwords are transmitted over HTTPS only
- Sessions expire after 24 hours of inactivity

### Best Practices
1. Use strong SSH passwords
2. Limit IP ranges for auto-discovery
3. Review discovered nodes before auto-adding
4. Regular security updates

---

## Support & Debugging

### Debug Mode
Add `?debug=true` to any URL for verbose logging

### Common Issues
| Issue | Solution |
|-------|----------|
| WebSocket disconnects | Check firewall allows WS protocol |
| Slow discovery | Reduce IP range or increase timeout |
| Node won't join | Verify SSH credentials and network connectivity |
| Transfer fails | Check disk space and network stability |

### Getting Help
- Logs: Check browser console (F12)
- API Docs: `/api/docs` for interactive testing
- Status: `/api/status` for system diagnostics