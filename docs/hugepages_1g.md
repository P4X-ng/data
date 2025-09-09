# 1GiB hugetlbfs setup and workflow (Ubuntu)

This document standardizes on a persistent 1GiB hugetlbfs mount at /mnt/huge1g and integrates with new Justfile targets.

Prereqs
- CPU must support 1GiB pages (x86_64 flag: pdpe1gb)
- Sufficient RAM to reserve 1–4 GiB for hugepages
- Root access for GRUB and /etc/fstab changes

Verify CPU capability
- grep -m1 -o 'pdpe1gb' /proc/cpuinfo || echo 'pdpe1gb not found (1GiB pages may be unsupported)'

Reserve 1GiB hugepages at boot (persistent)
1) Backup GRUB
   - sudo cp -av /etc/default/grub /etc/default/grub.bak-$(date -Iseconds)
2) Edit /etc/default/grub so GRUB_CMDLINE_LINUX includes:
   - default_hugepagesz=1G hugepagesz=1G hugepages=4 transparent_hugepage=never
   Adjust hugepages=N as needed for your memory budget.
3) Apply:
   - sudo update-grub

Persistent mount for 1GiB pages
1) Backup fstab
   - sudo cp -av /etc/fstab /etc/fstab.bak-$(date -Iseconds)
2) Add mount (create mount point first):
   - sudo mkdir -p /mnt/huge1g
   - echo 'hugetlbfs /mnt/huge1g hugetlbfs mode=1777,pagesize=1G 0 0' | sudo tee -a /etc/fstab

Reboot and verify
- sudo reboot
- After login: just hugepages-status
  Expect:
  - /mnt/huge1g mounted (hugetlbfs, pagesize=1G)
  - HugePages_Total for 1048576kB > 0

Using 1GiB in PacketFS
- Build: just build-net-pfs-gram; just build-blueprint-native; just build-cpu-baseline
- Guided flow: just pfs-1g
- Quick smoke:
  - Server: just run-pfs-tcp-1g-server port=8433 blob_bytes=1073741824
  - Client: just run-pfs-tcp-1g-client host=127.0.0.1 port=8433 blob_bytes=1073741824
- Benchmark:
  - just bench-blueprint-fast-1g
  - Or full sweep: just bench-blueprint-maxwin-1g

Notes
- If mount fails before reboot, ensure the 1GiB pages are reserved at boot.
- If you over-reserve and boot fails, reduce hugepages=N in GRUB.
- Tools also support /dev/hugepages; this project standardizes on /mnt/huge1g for clarity.

