#!/usr/bin/env bash
set -euo pipefail
# Wrapper for milkshake_aws_word.py with optional region
# Usage: run_word.sh <target_ip> <base> <bits> <pattern> <pps> <seconds> <log_group> <eni> <minutes> [region] [prefer_action] [threshold]

TARGET=${1:-}
BASE=${2:-}
BITS=${3:-16}
PAT=${4:-}
PPS=${5:-2000}
SECONDS=${6:-2}
LG=${7:-}
ENI=${8:-}
MINS=${9:-5}
REG=${10:-}
PREF=${11:-ACCEPT}
THR=${12:-1}

if [[ -z "$TARGET" || -z "$BASE" || -z "$PAT" || -z "$LG" || -z "$ENI" ]]; then
  echo "usage: $0 <target_ip> <base> <bits> <pattern> <pps> <seconds> <log_group> <eni> <minutes> [region] [prefer_action] [threshold]" >&2
  exit 2
fi

PY=/home/punk/.venv/bin/python
SCRIPT=scripts/cloud_milkshake/milkshake_aws_word.py

ARGS=(--target-ip "$TARGET" --base-port "$BASE" --bits "$BITS" --pattern "$PAT" --pps "$PPS" --seconds "$SECONDS" --log-group "$LG" --interface-id "$ENI" --minutes "$MINS" --prefer-action "$PREF" --threshold "$THR")
if [[ -n "$REG" ]]; then ARGS+=(--region "$REG"); fi

exec "$PY" "$SCRIPT" "${ARGS[@]}"