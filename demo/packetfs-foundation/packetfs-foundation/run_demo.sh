#!/bin/bash
echo "🚀💎⚡ PACKETFS DEMONSTRATION SUITE ⚡💎🚀"
echo "================================================"
echo ""

echo "📁 Available demo files:"
ls -lh /tmp/packetfs-foundation/demos/

echo ""
echo "🗜️  Testing PacketFS compression..."

for file in /tmp/packetfs-foundation/demos/*; do
    if [ -f "$file" ]; then
        echo ""
        echo "🔍 Processing: $(basename $file)"
        /tmp/packetfs-foundation/pfs-compress "$file"
    fi
done

echo ""
echo "⚡ Testing PacketFS execution..."

for pfs_file in /tmp/packetfs-foundation/demos/*.pfs; do
    if [ -f "$pfs_file" ]; then
        echo ""
        echo "🚀 Executing: $(basename $pfs_file)"
        /tmp/packetfs-foundation/pfs-exec "$pfs_file"
    fi
done

echo ""
echo "✅ PACKETFS DEMONSTRATION COMPLETE!"
echo "💎 Network packets = Assembly instructions!"
echo "🌐 Files = Compressed packet streams!"
echo "⚡ Execution = Wire-speed packet processing!"
