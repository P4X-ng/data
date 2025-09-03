#!/usr/bin/env python3
"""
PacketFS Telnet Interface Demo
Demonstrates the rsync-like telnet protocol for file transfers
"""

import os
import sys
import time
import subprocess
import threading
import tempfile
from pathlib import Path

# Add tools to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tools'))

def create_test_files():
    """Create sample files for testing"""
    test_dir = Path("/tmp/pfs_demo")
    test_dir.mkdir(exist_ok=True)
    
    # Create various test files
    files = {
        "small.txt": "This is a small test file.",
        "medium.log": "\n".join([f"Log entry {i}: Something happened at {time.time()}" for i in range(1000)]),
        "config.json": '{"server": "localhost", "port": 8337, "features": ["sync", "transfer"]}',
        "binary.bin": os.urandom(1024 * 10)  # 10KB binary file
    }
    
    # Create nested directories
    subdir = test_dir / "subdir"
    subdir.mkdir(exist_ok=True)
    
    for filename, content in files.items():
        filepath = test_dir / filename
        if isinstance(content, str):
            filepath.write_text(content)
        else:
            filepath.write_bytes(content)
    
    # Create files in subdirectory
    (subdir / "nested.txt").write_text("This file is in a subdirectory")
    
    print(f"📁 Created test files in {test_dir}")
    return test_dir

def demo_cli_usage():
    """Demonstrate CLI usage examples"""
    print("\n" + "="*60)
    print("🔧 PacketFS CLI (pfs) Examples")
    print("="*60)
    
    examples = [
        # Basic usage examples
        ("Show help", "./tools/pfs --help"),
        
        # Server mode 
        ("Start server", "./tools/pfs --server --port 8337"),
        
        # Shell mode
        ("Interactive shell", "./tools/pfs --shell localhost"),
        
        # Transfer examples  
        ("Download file", "./tools/pfs user@host:/remote/file.txt ./local.txt"),
        ("Upload file (dry run)", "./tools/pfs -n ./local.txt user@host:/remote/path/"),
        
        # Benchmark
        ("Performance test", "./tools/pfs --benchmark 100MB localhost"),
    ]
    
    for description, command in examples:
        print(f"\n{description}:")
        print(f"  $ {command}")
    
    print(f"\n💡 Note: These are example commands. The server needs to be running for transfers.")

def demo_telnet_usage():
    """Demonstrate telnet interface usage"""
    print("\n" + "="*60)
    print("📡 PacketFS Telnet Server Examples")
    print("="*60)
    
    print("\n1. Start the telnet server:")
    print("  $ python tools/telnet_server.py --host 0.0.0.0 --port 2323")
    
    print("\n2. Connect with standard telnet client:")
    print("  $ telnet localhost 2323")
    
    print("\n3. Available commands in telnet session:")
    commands = [
        ("help", "Show available commands"),
        ("ls [path]", "List directory contents"),
        ("pwd", "Print working directory"),
        ("cd <path>", "Change directory"), 
        ("mkdir <dir>", "Create directory"),
        ("rm <file>", "Remove file or directory"),
        ("stat <file>", "Show file information"),
        ("get <remote> [local]", "Download file"),
        ("put <local> [remote]", "Upload file"),
        ("transfer <src> <dst>", "Transfer file (rsync-like)"),
        ("sync <src> <dst>", "Sync directories (rsync-like)"),
        ("benchmark [size]", "Run performance test"),
        ("exit", "Exit session"),
    ]
    
    for cmd, desc in commands:
        print(f"  {cmd:<25} - {desc}")

def demo_rsync_syntax():
    """Demonstrate rsync-like syntax examples"""
    print("\n" + "="*60)  
    print("🔄 rsync-like Syntax Examples")
    print("="*60)
    
    print("\nBoth the CLI and telnet interface support rsync-like syntax:")
    
    syntax_examples = [
        # Local to remote
        ("Upload file", "transfer /local/file.txt user@host:/remote/path/"),
        ("Upload directory", "sync /local/dir/ user@host:/remote/dir/"),
        
        # Remote to local  
        ("Download file", "transfer user@host:/remote/file.txt /local/path/"),
        ("Download directory", "sync user@host:/remote/dir/ /local/dir/"),
        
        # Local to local (for testing)
        ("Local copy", "transfer /source/file.txt /dest/file.txt"),
        ("Local sync", "sync /source/dir/ /dest/dir/"),
        
        # Advanced options (CLI)
        ("Dry run", "pfs -n /local/ user@host:/remote/"),
        ("Verbose", "pfs -v /local/ user@host:/remote/"),
        ("Recursive", "pfs -r /local/dir/ user@host:/remote/dir/"),
    ]
    
    for description, example in syntax_examples:
        print(f"\n{description}:")
        print(f"  {example}")

def run_basic_test():
    """Run a basic functionality test"""
    print("\n" + "="*60)
    print("🧪 Basic Functionality Test")
    print("="*60)
    
    # Create test files
    test_dir = create_test_files()
    
    print(f"\n✅ Test files created in {test_dir}")
    
    # Show directory contents
    print(f"\n📋 Test directory contents:")
    for root, dirs, files in os.walk(test_dir):
        level = root.replace(str(test_dir), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = os.path.join(root, file)
            size = os.path.getsize(file_path)
            print(f"{subindent}{file} ({size} bytes)")
    
    # Test CLI help
    print(f"\n🔧 Testing CLI help:")
    try:
        result = subprocess.run([sys.executable, "tools/pfs", "--help"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ CLI help works")
            print("First few lines:")
            lines = result.stdout.split('\n')[:5]
            for line in lines:
                print(f"  {line}")
        else:
            print(f"❌ CLI help failed: {result.stderr}")
    except Exception as e:
        print(f"❌ CLI test failed: {e}")
    
    # Test dry run
    print(f"\n🏃 Testing dry run:")
    try:
        result = subprocess.run([
            sys.executable, "tools/pfs", "-n",
            str(test_dir / "small.txt"), 
            "user@localhost:/tmp/destination.txt"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Dry run works")
            print("Output:")
            for line in result.stdout.split('\n')[:3]:
                if line.strip():
                    print(f"  {line}")
        else:
            print(f"❌ Dry run failed: {result.stderr}")
    except Exception as e:
        print(f"❌ Dry run test failed: {e}")

def interactive_demo():
    """Interactive demo allowing user to test features"""
    print("\n" + "="*60)
    print("🎮 Interactive Demo Mode")
    print("="*60)
    
    while True:
        print("\nChoose a demo option:")
        print("1. Start telnet server (port 2323)")
        print("2. Start PFS file transfer server (port 8337)")
        print("3. Create test files")
        print("4. Test CLI commands")
        print("5. Show usage examples")
        print("0. Exit")
        
        choice = input("\nEnter choice (0-5): ").strip()
        
        if choice == "0":
            print("👋 Goodbye!")
            break
        elif choice == "1":
            print("\n🚀 Starting telnet server on port 2323...")
            print("Use: telnet localhost 2323")
            print("Press Ctrl+C to stop")
            try:
                subprocess.run([sys.executable, "tools/telnet_server.py", "--port", "2323"])
            except KeyboardInterrupt:
                print("\n✅ Telnet server stopped")
        elif choice == "2":
            print("\n🚀 Starting PFS server on port 8337...")
            print("Press Ctrl+C to stop")
            try:
                subprocess.run([sys.executable, "tools/packetfs_file_transfer.py", "server"])
            except KeyboardInterrupt:
                print("\n✅ PFS server stopped")
        elif choice == "3":
            create_test_files()
        elif choice == "4":
            run_basic_test()
        elif choice == "5":
            demo_cli_usage()
            demo_telnet_usage()
            demo_rsync_syntax()
        else:
            print("❌ Invalid choice")

def main():
    print("🎯 PacketFS Telnet Interface Demo")
    print("==================================")
    
    print("\nThis demo shows the new telnet protocol interface for PacketFS")
    print("that provides rsync-like syntax for familiar file transfers.")
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_demo()
    else:
        # Run all demos
        demo_cli_usage()
        demo_telnet_usage() 
        demo_rsync_syntax()
        run_basic_test()
        
        print(f"\n🎮 For interactive mode, run:")
        print(f"  python demo_telnet.py --interactive")

if __name__ == "__main__":
    main()
