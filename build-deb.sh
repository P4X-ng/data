#!/bin/bash
# Build script for creating packetfs-utils .deb package

set -e

echo "[*] Building packetfs-utils Debian package..."

# Colors (ASCII only)
INFO="[*]"
SUCCESS="[+]"
ERROR="[!]"

# Check dependencies
echo "$INFO Checking build dependencies..."
MISSING_DEPS=""

for dep in dpkg-buildpackage debhelper dh-python fakeroot; do
    if ! command -v $dep >/dev/null 2>&1; then
        MISSING_DEPS="$MISSING_DEPS $dep"
    fi
done

if [ -n "$MISSING_DEPS" ]; then
    echo "$ERROR Missing build dependencies:$MISSING_DEPS"
    echo "$INFO Install with: sudo apt install build-essential debhelper dh-python fakeroot"
    exit 1
fi

# Set version
VERSION="1.0.0"
ARCH=$(dpkg --print-architecture)
echo "$INFO Building version $VERSION for $ARCH"

# Clean previous builds
echo "$INFO Cleaning previous builds..."
rm -rf debian/packetfs-utils
rm -f ../packetfs-utils_*.deb
rm -f ../packetfs-utils_*.changes
rm -f ../packetfs-utils_*.buildinfo
rm -f ../packetfs-utils_*.dsc
rm -f ../packetfs-utils_*.tar.xz

# Create necessary directories
echo "$INFO Creating build directories..."
mkdir -p debian/source

# Create format file
echo "3.0 (native)" > debian/source/format

# Make rules executable
chmod +x debian/rules

# Create copyright file
cat > debian/copyright << 'EOF'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: packetfs-utils
Upstream-Contact: PacketFS Team <packetfs@example.com>
Source: https://github.com/packetfs/packetfs-utils

Files: *
Copyright: 2025 PacketFS Team
License: MIT
 Permission is hereby granted, free of charge, to any person obtaining a
 copy of this software and associated documentation files (the "Software"),
 to deal in the Software without restriction, including without limitation
 the rights to use, copy, modify, merge, publish, distribute, sublicense,
 and/or sell copies of the Software, and to permit persons to whom the
 Software is furnished to do so, subject to the following conditions:
 .
 The above copyright notice and this permission notice shall be included
 in all copies or substantial portions of the Software.
 .
 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
 OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
 CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
EOF

# Build the package
echo "$INFO Building Debian package..."
if dpkg-buildpackage -us -uc -b; then
    echo "$SUCCESS Build completed successfully!"
    
    # Move package to current directory
    if [ -f ../packetfs-utils_${VERSION}-1_${ARCH}.deb ]; then
        mv ../packetfs-utils_${VERSION}-1_${ARCH}.deb ./
        echo "$SUCCESS Package created: packetfs-utils_${VERSION}-1_${ARCH}.deb"
        
        # Show package info
        echo ""
        echo "$INFO Package Information:"
        dpkg-deb -I packetfs-utils_${VERSION}-1_${ARCH}.deb
        
        echo ""
        echo "$INFO Package Contents:"
        dpkg-deb -c packetfs-utils_${VERSION}-1_${ARCH}.deb | head -20
        echo "  ... (showing first 20 files)"
        
        echo ""
        echo "$SUCCESS Installation:"
        echo "  sudo dpkg -i packetfs-utils_${VERSION}-1_${ARCH}.deb"
        echo "  sudo apt-get install -f  # Install any missing dependencies"
        echo ""
        echo "$SUCCESS Usage after installation:"
        echo "  f3transfer send myfile.txt"
        echo "  sudo systemctl start packetfs-transfer"
        echo "  Browse to http://localhost:8811"
    fi
else
    echo "$ERROR Build failed!"
    echo "$INFO Check the build log above for errors"
    exit 1
fi

# Clean up build artifacts
echo "$INFO Cleaning up build artifacts..."
rm -f ../packetfs-utils_*.changes
rm -f ../packetfs-utils_*.buildinfo
rm -f ../packetfs-utils_*.dsc
rm -f ../packetfs-utils_*.tar.xz

echo "$SUCCESS Done!"