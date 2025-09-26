# Repository History Rewrite - Migration Guide

This repository’s history was rewritten to remove large generated artifacts (logs, pattern blobs, VM images, tarballs, etc.) and to bring the repo under GitHub’s size limits. Git LFS is enabled for future large binaries.

Current HEAD after rewrite: 8c45759f91
Remote: git@github.com:P4X-ng/data.git

What changed
- Purged large historical paths (examples):
  - logs/, logs/patterns/, experiment-logs/
  - src/patterns/ (pattern snapshots / large blobs)
  - plans/, iprog/, pfsmeta/
  - .vm/ and tarball images
  - Large binary extensions (*.bin, *.tar, *.tar.gz, *.zip, *.xz, *.pbb, *.pbb.xz, *.jsonl, *.pkl)
- Stripped blobs >50MB from history.
- Added Git LFS tracking for future large binaries.
- Added .gitignore rules to keep generated artifacts out of Git.

How collaborators should migrate

Option 1: Fresh clone (recommended)
1) Clone the cleaned repo:
   git clone git@github.com:P4X-ng/data.git
   cd data
2) Ensure LFS is ready, then fetch LFS objects if any:
   git lfs install
   git lfs pull

Option 2: Reset an existing clone
1) Update and hard reset to the new main:
   git fetch origin
   git reset --hard origin/main
2) Ensure LFS is ready, then pull LFS objects if any:
   git lfs install
   git lfs pull

Notes
- All local branches should be rebased on the new main.
- If you see missing LFS pointers, run:
  git lfs fetch --all && git lfs pull
- Generated artifacts (logs/, patterns, tarballs, VM images, etc.) are ignored going forward; keep them out of commits.
- A pre-commit hook is provided to block adding files larger than 50MB.
