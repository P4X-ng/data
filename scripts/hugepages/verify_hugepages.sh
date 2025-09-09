#!/usr/bin/env bash
set -euo pipefail

# scripts/hugepages/verify_hugepages.sh
# Purpose: Summarize hugepage status (2M and 1G), mounts, and kernel cmdline.

printf "== Kernel cmdline ==\n"
cat /proc/cmdline || true

printf "\n== CPU flag for 1G pages (pdpe1gb) ==\n"
grep -qm1 pdpe1gb /proc/cpuinfo && echo "pdpe1gb: present" || echo "pdpe1gb: not found"

printf "\n== /proc/meminfo (Huge*) ==\n"
grep -iE 'HugePages|Hugepagesize' /proc/meminfo || true

printf "\n== sysfs hugepages (nr/free/resv) ==\n"
for d in /sys/kernel/mm/hugepages/hugepages-*; do
  [ -d "$d" ] || continue
  sz=$(basename "$d" | sed -E 's/hugepages-([0-9]+)kB/\1 kB/')
  nr=$(cat "$d/nr_hugepages" 2>/dev/null || echo -)
  fr=$(cat "$d/free_hugepages" 2>/dev/null || echo -)
  rs=$(cat "$d/resv_hugepages" 2>/dev/null || echo -)
  printf "%12s : nr=%s free=%s resv=%s\n" "$sz" "$nr" "$fr" "$rs"
done

printf "\n== hugetlbfs mounts ==\n"
# Show mounts and page size options for /mnt/huge and /mnt/huge1g if present
awk '$3=="hugetlbfs" {print}' /proc/mounts | sed 's/ /\n  /g' || true

for m in /mnt/huge /mnt/huge1g; do
  if mountpoint -q "$m"; then
    printf "\nMount: %s\n" "$m"
    stat -f -c 'type=%T, blocks=%b, bsize=%s' "$m" || true
    echo "Options:"; findmnt -no OPTIONS "$m" 2>/dev/null || true
  else
    printf "\nMount: %s (not mounted)\n" "$m"
  fi
done

echo "\nDone."

