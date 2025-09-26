#!/bin/bash
# Build OS-Walk VM image

set -e

echo "Building OS-Walk Distributed OS VM..."

# Create base Alpine Linux with OS-Walk
mkdir -p vm-build/rootfs

# Download Alpine mini root filesystem
if [ ! -f "alpine-minirootfs.tar.gz" ]; then
    wget https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-minirootfs-3.19.0-x86_64.tar.gz -O alpine-minirootfs.tar.gz
fi

# Extract base system
cd vm-build/rootfs
tar -xzf ../../alpine-minirootfs.tar.gz

# Install packages
cat > etc/apk/repositories << EOF
https://dl-cdn.alpinelinux.org/alpine/v3.19/main
https://dl-cdn.alpinelinux.org/alpine/v3.19/community
EOF

# Chroot and install packages
sudo chroot . /bin/sh << 'CHROOT_EOF'
apk update
apk add python3 py3-pip redis fuse3 openssh-client curl jq
apk add qemu-guest-agent
pip3 install redis fuse-python hypercorn fastapi websockets
CHROOT_EOF

# Copy OS-Walk system
sudo cp -r ../../*.py .
sudo cp -r ../../f3-app .
sudo cp ../../oswalk usr/local/bin/
sudo chmod +x usr/local/bin/oswalk

# Create init system
sudo tee etc/init.d/oswalk << 'EOF'
#!/sbin/openrc-run

name="OS-Walk Distributed OS"
description="Network machines as one unified system"

depend() {
    need net redis
}

start() {
    ebegin "Starting OS-Walk"
    start-stop-daemon --start --background --exec /usr/local/bin/oswalk -- shell
    eend $?
}

stop() {
    ebegin "Stopping OS-Walk"
    start-stop-daemon --stop --exec /usr/local/bin/oswalk
    eend $?
}
EOF

sudo chmod +x etc/init.d/oswalk
sudo chroot . rc-update add oswalk default

# Create disk image
cd ..
qemu-img create -f qcow2 oswalk-root.qcow2 20G

# Install to disk (simplified)
echo "VM filesystem ready in vm-build/rootfs"
echo "To complete: create bootable ISO or install to qcow2 image"

echo "OS-Walk VM build complete!"
echo "Boot with: qemu-system-x86_64 -m 4G -smp 4 -hda oswalk-root.qcow2 -netdev user,id=net0,hostfwd=tcp::8811-:8811 -device e1000,netdev=net0"