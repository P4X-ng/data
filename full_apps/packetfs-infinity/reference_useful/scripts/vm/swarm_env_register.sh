#!/usr/bin/env bash
set -euo pipefail

# Env-driven swarm register
# Vars: BASE_PORT (9000), TOTAL (128), HOST (127.0.0.1), KIND (vm_http)

START_PORT=${BASE_PORT:-9000}
COUNT=${TOTAL:-128}
HOST=${HOST:-127.0.0.1}
KIND=${KIND:-vm_http}

/home/punk/.venv/bin/python scripts/vm/register_swarm.py --start-port "$START_PORT" --count "$COUNT" --host "$HOST" --kind "$KIND"
