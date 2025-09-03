#!/usr/bin/env python3
"""
Network Test Deployment Script
"""
import subprocess
import time

REMOTE_HOST = "10.69.69.235"
REMOTE_USER = "punk"


def run_ssh_command(command):
    """Execute command on remote host"""
    full_cmd = f'ssh -A {REMOTE_USER}@{REMOTE_HOST} "{command}"'
    result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stdout, result.stderr


def deploy_and_test():
    print("🚀 PacketFS Real Network Testing Suite")
    print("=" * 50)

    # Test connectivity
    print("📡 Testing connectivity...")
    success, stdout, stderr = run_ssh_command('echo "Remote connected!"')
    if success:
        print(f"✅ {stdout.strip()}")
    else:
        print(f"❌ Connection failed: {stderr}")
        return

    # Test remote PacketFS
    print("📊 Testing PacketFS on remote ARM64...")
    success, stdout, stderr = run_ssh_command(
        'cd ~/packetfs-remote && source .venv/bin/activate && python -c "import packetfs.protocol; print("PacketFS works on ARM64!")"'
    )
    if success:
        print(f"✅ {stdout.strip()}")
    else:
        print(f"❌ Remote test failed: {stderr}")

    print("🏁 Testing completed!")


if __name__ == "__main__":
    deploy_and_test()
