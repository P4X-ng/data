# staging/

Purpose
- Holds "almost done" code that is converging to production quality but not yet promoted to src/.
- Use this area to stabilize APIs, polish CLI surfaces, and finish tests.

Guidelines
- Keep staging changes small and documented; link to owning Just targets.
- When stable, move to src/ with minimal path churn (update includes/targets).
- Do not mix demo/legacy content here — keep it under dev/ or legacy/.

Suggested candidates (do not move blindly; verify includes and paths first)
- src/dev/wip/native/* utilities that have stabilized CLIs (pfs_shm_ring_bench, etc.).
- Shared program encoders/decoders for memory-level programs once CLI freezes.
- Any new pfs_fastpath user-space utilities approaching final UAPI.

Promotion checklist
- APIs documented
- Just targets present with help
- Tests cover basic flows
- Lint/format clean
- Benchmarks recorded under logs/ with parameters