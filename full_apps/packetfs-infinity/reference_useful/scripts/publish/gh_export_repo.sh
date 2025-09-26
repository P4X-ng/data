#!/usr/bin/env bash
set -euo pipefail
# Export docs/ into a standalone data repo working directory for private hosting.
# This does NOT configure remotes or push; you can add origin and push manually.
# Usage: gh_export_repo.sh <source_docs_dir> <target_repo_dir> [branch]

SRC=${1:-docs}
DST=${2:-../pfs-index}
BR=${3:-main}

if [[ ! -d "$SRC" ]]; then
  echo "[error] source docs dir not found: $SRC" >&2
  exit 2
fi

mkdir -p "$DST"
rsync -av --delete "$SRC/" "$DST/" >/dev/null

cd "$DST"
if [[ ! -d .git ]]; then
  git init -b "$BR"
fi

git add .
if ! git diff --cached --quiet; then
  git commit -m "PacketFS: publish manifests $(date -u +%Y-%m-%dT%H:%M:%SZ)"
else
  echo "[info] no changes to commit"
fi

echo "[ok] exported docs to $DST"
echo "Next steps:"
echo "  cd $DST && git remote add origin <your-private-repo-url> (first time)"
echo "  git push -u origin $BR"