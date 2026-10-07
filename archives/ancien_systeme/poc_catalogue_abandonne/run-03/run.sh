#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$P/../.." && pwd)"
source "$R/scripts/activate_local.sh"
export PYTHONPATH="$R${PYTHONPATH:+:$PYTHONPATH}"
exec "$R/.venv/bin/python" "$P/run.py"
