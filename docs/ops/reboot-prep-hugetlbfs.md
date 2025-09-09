# Reboot Prep: hugetlbfs with 2MB and 1GB pages (Ubuntu)

Purpose
- Reserve 1GB and 2MB huge pages at boot, mount hugetlbfs for both, and verify after reboot. This enables testing 1GB-backed blobs under /mnt/huge1g and 2MB-backed under /mnt/huge.

Pre-flight
- CPU supports 1GB pages (x86_64 flag pdpe1gb). Check after reboot as well:
  - grep -m1 -o 'pdpe1gb' /proc/cpuinfo || echo 'pdpe1gb not found (1GB pages may be unsupported)'
- Ensure directories exist: /mnt/huge and /mnt/huge1g

1) Kernel command line (GRUB)
- Edit /etc/default/grub and ensure GRUB_CMDLINE_LINUX includes entries to reserve both sizes. Example (adjust counts):
  default_hugepagesz=2M hugepagesz=2M hugepages=2048 hugepagesz=1G hugepages=4
- Optional: to minimize THP interference during tests, append transparent_hugepage=never
- Apply and review:
  - sudo update-grub
  - sudo grub-mkconfig -o /boot/grub/grub.cfg (if needed on your distro)

2) fstab mounts (persistent)
- Add to /etc/fstab (create mount points first):
  hugetlbfs /mnt/huge   hugetlbfs mode=1777,pagesize=2M 0 0
  hugetlbfs /mnt/huge1g hugetlbfs mode=1777,pagesize=1G 0 0
- Then:
  - sudo mkdir -p /mnt/huge /mnt/huge1g

3) Reboot
- sudo reboot

4) Post-reboot verification
- Mounts (if not already auto-mounted):
  - sudo mount -a
- Quick checks:
  - mount | grep hugetlbfs
  - grep -i Huge /proc/meminfo | grep -E 'HugePages|Hugepagesize'
  - ls -l /sys/kernel/mm/hugepages/hugepages-*/nr_hugepages /sys/kernel/mm/hugepages/hugepages-*/free_hugepages
- Run the helper script:
  - bash scripts/hugepages/verify_hugepages.sh

5) Notes and rollback
- If 1GB pages fail to reserve, you’ll see nr_hugepages=0 under hugepages-1048576kB. Verify BIOS settings and pdpe1gb CPU flag.
- To reduce reserved pages, lower hugepages= counts in GRUB and reboot.
- If you prefer runtime allocation for 2MB pages (less reliable for 1GB), you can adjust:
  - echo N | sudo tee /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
  But for 1GB pages, reserving at boot is strongly recommended.

Tomorrow’s quick checklist
- Reboot with new GRUB params
- Verify hugepages via verify_hugepages.sh
- Re-run max-win sweep on /mnt/huge1g and compare to /mnt/huge
- Patch benchmark to use mmap prefill for hugetlbfs to avoid write() EINVAL

