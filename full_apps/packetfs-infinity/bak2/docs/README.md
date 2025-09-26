# PacketFS GitHub Pages (control plane)

This directory can be published via GitHub Pages to distribute PacketFS metadata:
- super_manifest.json
- providers/*.json
- windows/*.jsonl.gz (chunked window maps)

Build manifests from a local file (POC):

```
just dev-gh-build-manifests path=/dev/shm/pfs_blob.bin base_url=https://USER.github.io/pfs-index/data/sha256/<digest>.bin
```

Then commit and push. Enable Pages on this repo or copy docs/ into a `pfs-index` repo with Pages enabled.