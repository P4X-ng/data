# DANGER_ONLY_FOR_TESTING_PURPOSES

This directory contains real, potentially dangerous tooling or datasets that are kept ONLY for explicit, manual testing.

Safety policies:
- NEVER execute anything here in production environments.
- No automation should traverse or run files from this directory.
- Use only on isolated, disposable machines or containers.
- Some items may require root; follow the project rule to chown back to punk:punk after any privileged operations.

Classification notes:
- Real but hazardous: vfio binding helpers, raw /sys interaction, system cloners, password/crypto target generators, password crackers, etc.
- Fictional/marketing or emulation content remains under fake_trash/ (kept only for provenance, not for execution).

Test exclusion:
- Pytest/CI should exclude this directory from discovery.
- Do not import modules from here into realsrc/.

Proceed at your own risk.

