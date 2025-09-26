# OSv Scanner Container

What this is
- A small container that boots an OSv image via qemu and forwards flags to the OSv app.
- Intended to run with host networking and /dev/kvm for speed.

Build
- Provide your OSv image path at build time (raw or qcow converted to raw).
  ```bash
  podman build -t osv-scanner:latest \
    --build-arg OSV_IMAGE=./osv.img \
    -f containers/osv-scanner/Containerfile .
  ```

Run (local)
- Host network + KVM (preferred):
  ```bash
  podman run --rm --net=host --device /dev/kvm \
    osv-scanner:latest --cidr 10.0.0.0/8 --ports 80,443 --rate 200000
  ```
- Without KVM (slower):
  ```bash
  podman run --rm --net=host osv-scanner:latest --cidr 10.0.0.0/8 --ports 80,443
  ```

Notes
- The OSv image should boot into your scanner entrypoint and parse the flags passed after the image boot. If your image expects different arguments, adjust run.sh or your OSv app accordingly.
- For larger deployments, push to a local registry and have VMs pull it on boot.
