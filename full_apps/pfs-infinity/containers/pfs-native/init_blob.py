#!/usr/bin/env python3
# Initializes a deterministic VirtualBlob for PacketFS translator stage
# Keeps imports independent of packaging by using /packetfs/src
import sys
sys.path.insert(0, "/packetfs/src")

from packetfs.filesystem.virtual_blob import VirtualBlob  # noqa: E402


def main():
    name = "pfs_core"
    size = 33554432  # 32 MiB (fits typical /dev/shm in build containers)
    seed = 1337
    vb = VirtualBlob(name, size, seed)
    vb.create_or_attach(create=True)
    vb.ensure_filled()
    print(f"Created blob: {vb.size} bytes (name={name}, seed={seed})")


if __name__ == "__main__":
    main()
