#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/activate_local.sh
exec "$CONVOKIT_PYTHON" poc/dlg-13/run.py
