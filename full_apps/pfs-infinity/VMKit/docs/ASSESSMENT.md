# Assessment and Cleanup Plan (VMKit Root)

Status: initialized Quickemu UX layer.

Performed:
- Added root Justfile with simple commands: doctor, setup, quickget, new, list, up, stop, ssh, delete, clean
- Added scripts: scripts/check-virt.sh (doctor), scripts/ensure-deps.sh (setup)
- Created standard layout: vms/, downloads/, templates/, scripts/, docs/
- Added templates: generic-linux.conf.tmpl, generic-windows.conf.tmpl
- Hygiene: .gitignore, .editorconfig, .gitattributes
- Docs: docs/README.md, docs/UX_CONTRACT.md, docs/TROUBLESHOOTING.md

Notes/Constraints captured from project rules:
- Prefer Podman over Docker (no Docker-only workflows introduced)
- Central Python venv at /home/punk/.venv for Python tooling (not needed for this shell-based layer)
- No demo code executed by default; any demo content to live under demo/
- Rebuild containers when big changes happen (N/A here)
- AUTOMATION.txt exists under vmkit/ (subdir). We implemented non-interactive scripts but avoided automatic system changes without INSTALL=1.

To-Do (follow-ups):
- Add bats tests for doctor and Justfile CLI in tests/ (non-interactive simulation)
- Optional CI workflow for basic checks
- If legacy scattered .conf/.qcow2 exist, add migration helper to consolidate into vms/
