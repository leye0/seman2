#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SEMAN2_ROOT/scripts/activate_local.sh"
exec "$SEMAN2_ROOT/.venv/bin/python" "$SEMAN2_ROOT/poc/sys-09/run.py"
