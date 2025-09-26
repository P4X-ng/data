WARP.md — VMKit (subproject)

Use the central venv and keep commands reproducible.

Quick commands
- List tasks in this dir: just --list (or open this file)
- Run tests (preferred): /home/punk/.venv/bin/pytest -v
- Clean test VMs: /home/punk/.venv/bin/python -c "from vmkit import SecureVM; SecureVM.cleanup_test_vms()"

Notes
- Respect repo rules: Podman > Docker; no demo code mixed with production; keep complex logic in scripts/.
- For Quickemu and orchestration, use the parent VMKit/Justfile.
