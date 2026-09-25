#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SEMAN2_ROOT/scripts/activate_local.sh"
export HF_HOME="$SEMAN2_ROOT/.local/share/huggingface"
exec "$SEMAN2_ROOT/.venv-rst/bin/python" "$@"

