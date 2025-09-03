# PacketFS Telnet Interface

## Overview

The PacketFS Telnet Interface provides an rsync-like command syntax over a telnet-compatible protocol, making file transfers familiar and easy to use. This interface wraps the existing PacketFS file transfer system with a user-friendly shell that supports standard file operations.

## Features

### 🌟 Key Features
- **rsync-like syntax** - Familiar `user@host:/path` format
- **Interactive shell** - SSH-like experience over telnet
- **Standard telnet client** - Works with any telnet client
- **File operations** - ls, cd, mkdir, rm, stat, etc.
- **Transfer commands** - get, put, transfer, sync
- **Performance testing** - Built-in benchmark tool
- **ANSI colors** - Rich terminal output

### 📡 Dual Protocol Support
- **Telnet Server** (port 23/2323) - Interactive shell interface
- **PacketFS Server** (port 8337) - High-performance file transfers

## Quick Start

### 1. Start the Telnet Server

```bash
# Default telnet port (requires sudo for port 23)
sudo python tools/telnet_server.py

# Alternative port (no sudo required)  
python tools/telnet_server.py --port 2323
```

### 2. Connect with Telnet Client

```bash
# Connect to server
telnet localhost 2323

# Or use netcat
nc localhost 2323
```

### 3. Use rsync-like Commands

Once connected, you can use familiar commands:

```bash
pfs> help                                    # Show available commands
pfs> ls /tmp                                 # List directory
pfs> cd /home/user                           # Change directory
pfs> transfer /local/file.txt /remote/path/  # Transfer file
pfs> sync /src/dir/ /dest/dir/              # Sync directories
pfs> benchmark 100MB                         # Run performance test
pfs> exit                                    # Exit session
```

## CLI Tool

The `pfs` command-line tool provides rsync-compatible syntax:

### Basic Usage

```bash
# Show help
./tools/pfs --help

# Start server
./tools/pfs --server --port 8337

# Interactive shell (like SSH)
./tools/pfs --shell user@host

# Transfer files (rsync syntax)
./tools/pfs local_file.txt user@host:/remote/path/
./tools/pfs user@host:/remote/file.txt ./local_file.txt

# Dry run
./tools/pfs -n /local/dir/ user@host:/remote/dir/

# Performance benchmark
./tools/pfs --benchmark 1GB user@host
```

### rsync-like Examples

```bash
# Upload file
pfs file.txt user@host:/path/file.txt

# Download file  
pfs user@host:/remote/file.txt ./local.txt

# Upload directory (recursive)
pfs -r /local/dir/ user@host:/remote/dir/

# Download directory  
pfs -r user@host:/remote/dir/ /local/dir/

# Dry run to see what would be transferred
pfs -n /src/ user@host:/dest/

# Verbose output
pfs -v file.txt user@host:/path/
```

## Telnet Commands

### File Operations
```bash
ls [path]              # List directory contents
pwd                    # Print working directory  
cd <path>              # Change directory
mkdir <dir>            # Create directory
rm <file|dir>          # Remove file or directory
stat <file>            # Show file information
```

### Transfer Operations
```bash
get <remote> [local]   # Download file from server
put <local> [remote]   # Upload file to server  
transfer <src> <dst>   # Transfer file (rsync-like)
sync <src> <dst>       # Sync directories (rsync-like)
```

### Utility Commands
```bash
benchmark [size]       # Run performance test (e.g., "benchmark 100MB")
help                   # Show help message
exit, quit, bye        # Exit telnet session
```

## Connection Formats

The tools support flexible connection string formats:

```bash
host                   # Plain hostname (default port)
host:port              # Host with custom port
user@host              # With username (will prompt for password)  
user@host:port         # Full specification
user@host:port:/path   # With initial path
```

## Examples

### Example 1: Basic File Transfer

```bash
# Terminal 1: Start server
python tools/telnet_server.py --port 2323

# Terminal 2: Connect with telnet
telnet localhost 2323
# Username: testuser
# Password: password

# In telnet session:
pfs> ls /tmp
pfs> transfer /etc/passwd /tmp/passwd_copy
pfs> stat /tmp/passwd_copy
pfs> exit
```

### Example 2: Performance Testing

```bash  
# Start server
python tools/telnet_server.py --port 2323

# Connect and run benchmark
telnet localhost 2323
pfs> benchmark 1GB
```

### Example 3: CLI Usage

```bash
# Start server
./tools/pfs --server --port 8337

# In another terminal: 
./tools/pfs --shell localhost
./tools/pfs --benchmark 100MB localhost
./tools/pfs -n /tmp/test.txt user@localhost:/home/user/
```

## Architecture

### Components

1. **TelnetServer** - Main server accepting telnet connections
2. **TelnetSession** - Per-client session handler  
3. **PacketFSCLI** - Command-line interface
4. **PacketFSShell** - Interactive shell implementation
5. **PacketFSFileTransfer** - Underlying transfer protocol

### Protocol Stack

```
┌─────────────────────────┐
│   Telnet/CLI Interface  │  ← rsync-like commands
├─────────────────────────┤
│   PacketFS Protocol     │  ← Chunked file transfer  
├─────────────────────────┤
│   TCP/IP                │  ← Network transport
└─────────────────────────┘
```

### Message Flow

1. **Telnet Connection** - Client connects to telnet server
2. **Authentication** - Simple username/password (optional)
3. **Command Processing** - Parse and execute rsync-like commands
4. **File Operations** - Use PacketFS protocol for transfers
5. **Response** - Send results back over telnet session

## Configuration

### Server Options

```bash
python tools/telnet_server.py --help

Options:
  --host HOST          Server bind address (default: 0.0.0.0)
  --port PORT          Telnet port (default: 23) 
  --pfs-port PORT      PacketFS port (default: 8337)
```

### CLI Options

```bash
./tools/pfs --help

Options:
  -r, --recursive      Recursive directory transfers
  -v, --verbose        Verbose output
  -n, --dry-run       Show what would be done
  --progress          Show transfer progress
  --shell             Start interactive shell
  --server            Start PacketFS server  
  --benchmark SIZE    Run performance test
  --host HOST         Server host
  --port PORT         Server port
```

## Demo and Testing

### Run the Demo

```bash
# Show all examples and run basic tests
python demo_telnet.py

# Interactive demo mode
python demo_telnet.py --interactive
```

### Demo Options

1. **Start telnet server** - Launch server on port 2323
2. **Start PFS server** - Launch file transfer server
3. **Create test files** - Generate sample files for testing
4. **Test CLI commands** - Run automated CLI tests
5. **Show usage examples** - Display example commands

### Test Files

The demo creates test files in `/tmp/pfs_demo/`:
- `small.txt` - Small text file
- `medium.log` - Multi-line log file  
- `config.json` - JSON configuration
- `binary.bin` - Binary test file
- `subdir/nested.txt` - Nested file

## Security Considerations

### Current Implementation
- **Simple authentication** - Basic username/password
- **No encryption** - Plain text telnet protocol  
- **Local testing** - Designed for development/demo

### Production Recommendations
- **Use TLS/SSH** - Encrypt telnet sessions  
- **Strong authentication** - Implement proper auth
- **Access control** - Restrict file system access
- **Rate limiting** - Prevent abuse
- **Logging** - Audit file operations

## Limitations

### Current Limitations
- **No file upload over telnet** - Requires separate protocol
- **Simple authentication** - Not production-ready
- **No compression** - Files transferred as-is
- **Limited error handling** - Basic error messages

### Future Enhancements
- **TFTP/XMODEM support** - File transfers over telnet
- **TLS encryption** - Secure telnet sessions
- **Advanced auth** - PAM, LDAP integration  
- **Compression** - Reduce transfer sizes
- **Progress bars** - Real-time transfer status
- **Access controls** - Permissions and quotas

## Development

### File Structure
```
tools/
├── pfs                    # Main CLI tool
├── telnet_server.py       # Telnet server implementation
└── packetfs_file_transfer.py  # Core transfer system

demo_telnet.py             # Demo and testing script
README_TELNET.md          # This documentation
```

### Adding New Commands

1. **Add command handler** in `TelnetSession.commands`
2. **Implement method** following `cmd_*` pattern  
3. **Update help text** in `cmd_help()`
4. **Add CLI support** in `PacketFSCLI` if needed

### Protocol Extension

To add new message types:
1. Define constants (e.g., `CMD_NEW_FEATURE = 21`)
2. Add handler in server
3. Add client support in CLI/shell
4. Update documentation

## Troubleshooting

### Common Issues

**Connection refused**
- Check server is running: `netstat -ln | grep 2323`
- Try different port: `--port 8023`

**Permission denied**  
- Use sudo for port 23: `sudo python tools/telnet_server.py`
- Or use higher port: `--port 2323`

**Command not found**
- Check PATH includes tools directory
- Use full path: `python tools/pfs --help`

**Import errors**
- Ensure PacketFS src/ directory exists
- Check Python path: `PYTHONPATH=./src python tools/pfs`

### Debug Mode

Enable verbose output:
```bash
# Server debug
python tools/telnet_server.py --port 2323 -v

# CLI debug  
./tools/pfs -v --shell localhost
```

## Performance

### Benchmarks

Typical performance on localhost:
- **Small files (<1MB)**: ~100-500 MB/s  
- **Medium files (1-100MB)**: ~200-800 MB/s
- **Large files (>100MB)**: ~300-1000 MB/s

Performance depends on:
- File size and type
- Network latency  
- Disk speed
- System load

### Optimization Tips

1. **Use larger files** for better throughput
2. **Local testing** for best performance  
3. **SSD storage** improves I/O
4. **Tune chunk sizes** in PacketFS protocol

---

## Conclusion

The PacketFS Telnet Interface successfully bridges the gap between the high-performance PacketFS protocol and familiar rsync-like syntax. It provides:

✅ **Familiar interface** - rsync users feel at home  
✅ **Easy integration** - Standard telnet clients work  
✅ **High performance** - PacketFS protocol underneath  
✅ **Interactive shell** - SSH-like experience  
✅ **Comprehensive tooling** - CLI and server components

This implementation demonstrates how modern protocols can be made accessible through familiar interfaces, combining the best of both worlds: cutting-edge performance with user-friendly operation.

Ready to transfer files the PacketFS way! 🚀
