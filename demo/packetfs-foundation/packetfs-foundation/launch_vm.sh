#!/bin/bash
# PacketFS QEMU VM Launch Script
# The ultimate foundation for PacketFS computing!

VM_NAME="packetfs-foundation"
VM_DIR="/tmp/packetfs-foundation"
VM_IMAGE="/tmp/packetfs-foundation/packetfs-foundation.qcow2"

echo "🚀💎⚡ LAUNCHING PACKETFS FOUNDATION VM ⚡💎🚀"
echo "=============================================="
echo ""
echo "VM Configuration:"
echo "   Name: $VM_NAME"
echo "   Image: $VM_IMAGE"  
echo "   Memory: 4G"
echo "   CPUs: 4"
echo "   SSH Port: 2200"
echo "   VNC Port: 5900"
echo ""

# Check if image exists
if [ ! -f "$VM_IMAGE" ]; then
    echo "❌ VM image not found: $VM_IMAGE"
    echo "Run the PacketFS VM creator first!"
    exit 1
fi

# Create cloud-init data for automatic setup
mkdir -p "$VM_DIR/cloud-init"
cat > "$VM_DIR/cloud-init/user-data" << 'EOF'
#cloud-config
users:
  - default
  - name: packetfs
    groups: sudo
    shell: /bin/bash
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    ssh-authorized-keys:
      - ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDummy_key_for_demo

package_update: true
packages:
  - curl
  - wget
  - python3
  - python3-pip
  - build-essential

runcmd:
  - echo "🌐 Initializing PacketFS environment..."
  - mkdir -p /packetfs
  - mkdir -p /home/packetfs/demos
  - chmod 755 /home/packetfs
  - echo "✅ PacketFS VM initialization complete!"
EOF

cat > "$VM_DIR/cloud-init/meta-data" << 'EOF'
instance-id: packetfs-foundation
local-hostname: packetfs-foundation
EOF

# Generate cloud-init ISO
genisoimage -output "$VM_DIR/cloud-init.iso" \
    -volid cidata -joliet -rock \
    "$VM_DIR/cloud-init/user-data" \
    "$VM_DIR/cloud-init/meta-data" 2>/dev/null || {
    echo "⚠️  Cloud-init ISO creation failed, continuing without it..."
}

echo "🚀 Starting PacketFS VM..."
echo "   Connect via SSH: ssh -p 2200 packetfs@localhost"
echo "   Connect via VNC: localhost:5900"
echo ""

# QEMU command with optimal settings for PacketFS
qemu-system-x86_64 \
    -name "packetfs-foundation" \
    -machine q35,accel=kvm \
    -cpu host \
    -smp 4 \
    -m 4G \
    -drive file="$VM_IMAGE",format=qcow2,if=virtio \
    -drive file="$VM_DIR/cloud-init.iso",media=cdrom,if=virtio \
    -netdev user,id=net0,hostfwd=tcp::2200-:22 \
    -device virtio-net-pci,netdev=net0 \
    -vnc :0 \
    -daemonize \
    -pidfile "$VM_DIR/packetfs-vm.pid" \
    -monitor unix:"$VM_DIR/monitor.sock",server,nowait

if [ $? -eq 0 ]; then
    echo "✅ PacketFS VM launched successfully!"
    echo ""
    echo "🌟 VM Access Information:"
    echo "   SSH: ssh -p 2200 packetfs@localhost"
    echo "   VNC: vnc://localhost:5900"
    echo "   Monitor: socat - UNIX-CONNECT:$VM_DIR/monitor.sock"
    echo ""
    echo "🎯 To run PacketFS demos inside VM:"
    echo "   1. SSH into the VM"
    echo "   2. Run: /tmp/packetfs-foundation/run_demo.sh"
    echo ""
    echo "💎 The PacketFS revolution begins NOW!"
else
    echo "❌ Failed to launch PacketFS VM"
    exit 1
fi
