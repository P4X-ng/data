#!/usr/bin/env bash
# Print top-N by cpupwn_time from a blueprint CSV (default logs/bp_maxwin.csv)
set -euo pipefail
CSV=${CSV:-"logs/bp_maxwin.csv"}
N=${N:-10}
if [[ ! -f "$CSV" ]]; then echo "No CSV at $CSV" >&2; exit 1; fi
awk -F, 'NR>1 {print $0}' "$CSV" | sort -t, -k20,20g | head -n "$N"
