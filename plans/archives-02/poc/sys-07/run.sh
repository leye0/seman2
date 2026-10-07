#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT/scripts/activate_local.sh"
exec "$ROOT/.venv/bin/python" "$ROOT/poc/sys-07/run.py"
