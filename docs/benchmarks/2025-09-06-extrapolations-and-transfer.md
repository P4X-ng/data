# Extrapolations and Transfer Implications (based on 2MB hugepages run)

Date: 2025-09-06
Sources: logs/bp_maxwin_huge2m_dumbcpu.csv; prior THP and tuned-CPU baselines
Note: These are planning estimates based on observed measurements, not claims. Validate with real runs post-reboot.

Top-line measured compute throughput (current 2MB hugepages)
- Peak: ~10.49 GB/s (contig, seg_len=80, pCPU=400k, 8 threads, batch=8)
- Typical high: 9.0–10.5 GB/s across several contig/scatter configs with seg_len=80
- Larger segments (256, 4096) trend lower, often 4–8 GB/s; 8–16 threads generally beat 32

Projection: effect of 1GB hugepages
- Expectation: fewer TLB misses and better page-walk locality vs 2MB pages, but benefits are workload-dependent.
- Conservative envelope: +5% to +15% over the best 2MB results when the blob working set is truly hugepage-resident and access pattern is favorable.
  - If 2MB peak = 10.5 GB/s, projected 1GB peak ≈ 11.0–12.1 GB/s.
- Action: re-run the same sweep on /mnt/huge1g and compare apples-to-apples (same seg/pCPU/thread/batch grid) to confirm.

Scaling with data size (compute-bound estimate)
- Assuming ~10.5 GB/s compute path (2MB) today; 1GB pages could raise this toward ~11–12 GB/s.
- Rough compute-only time T_compute ≈ Size / Throughput.
  - 400 MB → ~0.038 s (10.5 GB/s)
  - 10 GB → ~0.95 s
  - 100 GB → ~9.5 s

Network interplay and “wire vs compute” break-even
- Let N = network line rate (GB/s), C = compute throughput (GB/s), r = fraction of payload that must be sent on the wire after dedupe/gram-reuse (0..1).
- Overlapped pipeline time ≈ max( r·Size / N, Size / C ). Break-even r* occurs when r·Size / N = Size / C → r* = N / C.
- With C ≈ 10.5 GB/s (today) and C ≈ 12 GB/s (1GB pages optimistic):
  - 10GbE (1.25 GB/s): r* ≈ 0.12 (2MB) to 0.10 (1GB). If you can avoid sending ≥88–90% of bytes (r ≤ 10–12%), end-to-end becomes compute-bound; otherwise network-bound.
  - 25GbE (3.125 GB/s): r* ≈ 0.30 (2MB) to 0.26 (1GB). Avoid ≥70–74% of bytes to be compute-bound.
  - 40GbE (5.0 GB/s): r* ≈ 0.48 (2MB) to 0.42 (1GB). Avoid ≥52–58% of bytes to be compute-bound.
  - 100GbE (12.5 GB/s): r* ≈ 1.19 (2MB) to 1.04 (1GB). Since r ≤ 1, end-to-end will be compute-bound even when sending 100% of bytes; network won’t be the limiter at 100GbE.

Concrete 400MB example (10GbE)
- Baseline full copy (no reuse): 400 MB / 1.25 GB/s ≈ 0.32 s (network-bound). Compute pass (reconstruction) at 10.5 GB/s ≈ 0.038 s.
- With 90% reuse (r=0.10): network ≈ 0.032 s; compute ≈ 0.038 s → ~0.038 s total. Effective improvement over naive copy ≈ 8.4×.
- With 99% reuse (r=0.01): network ≈ 0.0032 s; compute ≈ 0.038 s → still ~0.038 s total (compute-bound). Diminishing returns once you’ve crossed break-even.

10 GB example (10GbE)
- Full copy: ~8.0 s (network-bound). Compute: ~0.95 s.
- 50% reuse (r=0.5): network ~4.0 s → total ~4.0 s (network-bound), ~2× faster than naive copy.
- 90% reuse (r=0.1): network ~0.8 s; compute ~0.95 s → total ~0.95 s (compute-bound), ~8.4× faster than naive copy.

About the extremely low wire_ratio observed in logs
- The blueprint-only local reconstruction path transmits almost nothing by design (e.g., constant ~417-byte control plane). That’s a local/loopback artifact and not representative of real remote sync.
- In real transfer, wire bytes = blueprint/grams + any segments not already present on the receiver. The actual r depends on content similarity and the pre-shared blob state.

What this likely means for transfer strategy
- On ≤10–25GbE links, prioritize maximizing reuse (low r) so that the pipeline flips to compute-bound quickly; once compute-bound, pushing compute throughput (1GB pages, thread tuning) lifts end-to-end speed.
- On ≥100GbE links, you’re compute-bound even at r=1; focus tuning on memory throughput (hugepages, NUMA locality, coalescing, seg_len) and executor efficiency.
- Small seg_len (80) performed best in our memory tests; validate on 1GB pages and consider wire-vs-CPU tradeoffs since very small segments can increase blueprint/gram cardinality.

Validation plan (tomorrow)
1) Reboot with 1GB hugepages reserved; verify with the provided script.
2) Re-run the max-win sweep on /mnt/huge1g using the same grid; produce logs/bp_maxwin_huge1g_dumbcpu.csv.
3) Generate top-15 report and compare to 2MB results; record observed delta (expect +5–15% in favorable cases).
4) Implement the mmap-based blob prefill to resolve hugetlbfs write() EINVAL before any native runs touching hugetlbfs.

Caveats
- All projections are planning aids; verify on target hardware, kernel, NUMA layout, and NIC. Differences in cache, memory channels, and IRQ/NAPI scheduling can materially change the outcome.
- The compute pass typically processes the full logical size even when wire bytes are small; thus, once network is no longer the bottleneck, improvements hinge on memory/compute throughput, not further wire reduction.

