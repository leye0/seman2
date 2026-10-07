#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
R="$(cd "$P/../.." && pwd)"
source "$R/scripts/activate_local.sh"
test -f "$R/poc/run-01/output/results.json" || "$R/poc/run-01/run.sh"
exec "$R/.venv/bin/python" "$P/run.py"
