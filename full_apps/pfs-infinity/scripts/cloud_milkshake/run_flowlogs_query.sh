#!/usr/bin/env bash
set -euo pipefail
# Wrapper for aws_flowlogs_query.py with optional region
# Usage: run_flowlogs_query.sh <log_group> <interface_id> <dstport> <protocol> <minutes> [region]

LG=${1:-}
ENI=${2:-}
PORT=${3:-}
PROTO=${4:-17}
MINS=${5:-5}
REG=${6:-}

if [[ -z "$LG" || -z "$ENI" || -z "$PORT" || -z "$PROTO" || -z "$MINS" ]]; then
  echo "usage: $0 <log_group> <interface_id> <dstport> <protocol> <minutes> [region]" >&2
  exit 2
fi

PY=/home/punk/.venv/bin/python
SCRIPT=scripts/cloud_milkshake/aws_flowlogs_query.py

if [[ -n "$REG" ]]; then
  exec "$PY" "$SCRIPT" --log-group "$LG" --interface-id "$ENI" --dstport "$PORT" --protocol "$PROTO" --minutes "$MINS" --region "$REG"
else
  exec "$PY" "$SCRIPT" --log-group "$LG" --interface-id "$ENI" --dstport "$PORT" --protocol "$PROTO" --minutes "$MINS"
fi