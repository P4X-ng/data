# Tests overview

There are two test trees. Keep them separate to avoid mixing demos with production.

- tests/: Production tests exercising src/ (canonical)
  - Run: /home/punk/.venv/bin/python -m pytest -q tests
- dev/working/tests/: Prototype/dev tests for work-in-progress tools
  - Run: just test-dev (PYTHONPATH=src:realsrc)

Guidelines
- Prefer unit tests for small, deterministic pieces
- Add performance tests under dev/working/tools with clear arguments and expected ranges
- Keep large artifacts out of the repo; emit summaries into logs/reports
