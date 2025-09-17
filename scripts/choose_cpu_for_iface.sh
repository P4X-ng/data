#!/usr/bin/env bash
# choose_cpu_for_iface.sh IFACE
# Prints a single CPU id to pin threads handling IFACE IRQs.
set -euo pipefail
IFACE=${1:-}
if [[ -z "$IFACE" ]]; then echo 0; exit 0; fi
# Gather IRQs referencing the interface
mapfile -t IRQS < <(awk -v IF="$IFACE" '/^ *[0-9]+:/{irq=$1; sub(":$","",irq); for(i=3;i<=NF;i++) if($i==IF) print irq; }' /proc/interrupts 2>/dev/null || true)
if [[ ${#IRQS[@]} -eq 0 ]]; then echo 0; exit 0; fi
candidates=()
for irq in "${IRQS[@]}"; do
  if [[ -r "/proc/irq/$irq/smp_affinity_list" ]]; then
    cpu_list=$(cat "/proc/irq/$irq/smp_affinity_list" | tr ',' ' ')
    first_cpu=${cpu_list%% *}
    candidates+=("$first_cpu")
  elif [[ -r "/proc/irq/$irq/smp_affinity" ]]; then
    mask=$(cat "/proc/irq/$irq/smp_affinity")
    # Convert hex mask to first set bit index
    # Use python if available, else fallback to shell
    if command -v python3 >/dev/null 2>&1; then
      cpu=$(python3 - <<PY
m=int("$mask",16)
print((m & -m).bit_length()-1 if m else 0)
PY
)
      candidates+=("$cpu")
    else
      candidates+=("0")
    fi
  fi
done
# Pick the most frequent candidate, fallback to first
if [[ ${#candidates[@]} -eq 0 ]]; then echo 0; exit 0; fi
chosen=$(printf "%s\n" "${candidates[@]}" | awk '{cnt[$1]++} END{best="";max=0; for(k in cnt){if(cnt[k]>max){max=cnt[k];best=k}} print best}')
if [[ -z "$chosen" ]]; then chosen=${candidates[0]}; fi
echo "$chosen"
