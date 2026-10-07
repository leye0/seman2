#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/activate_local.sh
exec env PYTHONPATH="$SOAR_BIN" LD_LIBRARY_PATH="$SOAR_BIN${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" python poc/soar-03/run.py
