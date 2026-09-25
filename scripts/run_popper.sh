#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SEMAN2_ROOT/scripts/activate_local.sh"
exec "$SEMAN2_ROOT/.venv-popper/bin/python" "$POPPER_HOME/popper.py" "$@"

