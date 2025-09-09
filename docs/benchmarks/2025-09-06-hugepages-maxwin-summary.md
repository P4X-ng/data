# Hugepage-backed Blueprint Benchmarks: 2MB results and next steps

Date: 2025-09-06
Location: logs/bp_maxwin_huge2m_dumbcpu.csv
Environment: Ubuntu, forced 2MB hugetlbfs for blob/output on /mnt/huge; mlock enabled; single-thread "dumb" CPU baseline for ops_ratio comparison; central venv at /home/punk/.venv.

Summary
- Broad max-win sweep completed using 2MB hugetlbfs on /mnt/huge, varying:
  - seg_len: 80, 256, 4096
  - pCPU: 200k, 400k, 800k, 1.3M, 2.6M
  - threads: 8, 16, 32
  - batch: 8, 16, 32
  - modes: contig, scatter
- Results saved: logs/bp_maxwin_huge2m_dumbcpu.csv
- Best observed: contig mode, seg_len=80, pCPU=400k, threads=8, batch=8 → ~10,492 MB/s, ops_ratio ≈ 3.793 vs the dumb single-thread baseline.
- Small segments (80) consistently deliver highest throughput and ops_ratio. Threads 8–16 often outperform 32.

Quick comparisons to prior runs
- THP (transparent hugepages): ~3.7 GB/s, ops_ratio ~0.27 (multi-thread CPU baseline)
- Forced 2MB hugepages with tuned multi-core CPU baseline: ~10.7 GB/s, ops_ratio ~0.71
- Current (2MB + dumb single-thread CPU baseline): ~10.5 GB/s, ops_ratio ~3.79 (reflects weaker baseline)

Notable top entries (examples)
- contig, seg=80, pcpu=400k, threads=8, batch=8 → 10492.47 MB/s, ops_ratio 3.793
- contig, seg=80, pcpu=400k, threads=8, batch=16 → 10033.73 MB/s, ops_ratio 3.627
- scatter, seg=80, pcpu=400k, threads=16, batch=16 → 10186.31 MB/s, ops_ratio 3.682
- contig, seg=80, pcpu=200k, threads=16, batch=8 → 9892.80 MB/s, ops_ratio 3.576

How to regenerate a ranked report
- Using the existing report tool (no state changes):
  PYTHONPATH=realsrc /home/punk/.venv/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_huge2m_dumbcpu.csv --top 15

Issue: hugetlbfs blob prefill via write() fails with OSError: [Errno 22]
- Observation: Native benchmark exit occurred during hugepage blob backing setup with os.write on a hugetlbfs file descriptor.
- Likely cause: hugetlbfs imposes stricter semantics; unaligned writes or certain write() patterns can return EINVAL. A portable approach is to populate via mmap and touch.

Planned fix: initialize hugepage-backed blob via mmap touching (no write())
- Strategy:
  1) Open the hugetlbfs file with O_CREAT|O_RDWR, set its length to the target size.
  2) mmap the whole region PROT_READ|PROT_WRITE, MAP_SHARED.
  3) Fill the deterministic xorshift pattern directly into the mmapped buffer in aligned blocks.
  4) msync(MS_SYNC) if desired; then munmap and close.
- Benefits: Ensures pages are actually faulted in with explicit touches; avoids write() alignment pitfalls; matches native code’s memory-first workflow.

Illustrative Python stub for mmap-based fill (pattern-only)
```python path=null start=null
import mmap, os, struct

PAGE = 2 * 1024 * 1024  # 2MB for example; use 1GiB on /mnt/huge1g
size = 100 * 1024 * 1024  # 100MB example
path = "/mnt/huge/pfs_blob"

# Ensure directory exists and mount is hugetlbfs before this (not shown)
fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
try:
    os.posix_fallocate(fd, 0, size)  # fallocate is fine; for hugetlbfs len must be multiple of huge page
    with mmap.mmap(fd, size, mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ, 0) as mm:
        # deterministic xorshift32 fill
        x = 0x12345678
        bs = 1 << 20  # 1MB chunk writes
        buf = bytearray(bs)
        off = 0
        while off < size:
            n = min(bs, size - off)
            # fill buf with a simple pattern; replace with existing xorshift impl
            for i in range(0, n, 4):
                x ^= (x << 13) & 0xFFFFFFFF
                x ^= (x >> 17)
                x ^= (x << 5) & 0xFFFFFFFF
                struct.pack_into("<I", buf, i, x & 0xFFFFFFFF)
            mm[off:off+n] = buf[:n]
            off += n
finally:
    os.close(fd)
```
Notes
- Ensure blob size is a multiple of the huge page size on the target mount (2MB or 1GB) before posix_fallocate/mmap.
- For 1GB mounts, use PAGE=1<<30 and verify /proc/meminfo HugePages values pre-run.

Tomorrow’s reboot checklist (summary)
1) Update GRUB kernel args to reserve 1GB (and optionally 2MB) hugetlbfs pages.
2) Create /etc/fstab entries for /mnt/huge (2M) and /mnt/huge1g (1G).
3) mkdir -p /mnt/huge /mnt/huge1g; update-grub; reboot.
4) After reboot: mount -a; run scripts/hugepages/verify_hugepages.sh and sanity-check output.
5) Re-run max-win sweep targeting /mnt/huge1g, same grid; save to logs/bp_maxwin_huge1g_dumbcpu.csv and generate report.
6) Patch benchmark to use mmap blob prefill before next native run.

Next actions (post-reboot)
- Run: PYTHONPATH=realsrc /home/punk/.venv/bin/python dev/working/tools/bench_blueprint_maxwin.py --size-mb 400 --blob-size-mb 100 --blob-name pfs_vblob_test --pcpu 200000,400000,800000,1300000,2600000 --seg 80,256,4096 --threads 8,16,32 --batch 8,16,32 --modes contig,scatter --hugehint --numa auto --ops-per-byte 1 --cpu-baseline --cpu-dumb --out logs/bp_maxwin_huge1g_dumbcpu.csv
- Then report: PYTHONPATH=realsrc /home/punk/.venv/bin/python dev/working/tools/blueprint_report.py --in logs/bp_maxwin_huge1g_dumbcpu.csv --top 15

Open items
- Clean shared_memory warnings in blueprint path.
- Implement mmap prefill for hugetlbfs blob creation.
- Consolidate cross-run comparison table (THP vs 2M tuned-CPU vs 2M dumb-CPU vs 1G).

