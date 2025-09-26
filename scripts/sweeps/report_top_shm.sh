#!/usr/bin/env bash
# Print top-N by cpupwn_time from an SHM sweep CSV
set -euo pipefail
CSV=${CSV:-"logs/reports/shm_maxwin_sweep_big.csv"}
N=${N:-10}
if [[ ! -f "$CSV" ]]; then echo "No CSV at $CSV" >&2; exit 1; fi
# Columns: ... cpupwn_time is column 10
awk -F, 'NR>1 && $10 != "NA" {printf "%s\n", $0}' "$CSV" | sort -t, -k10,10g | head -n "$N"
