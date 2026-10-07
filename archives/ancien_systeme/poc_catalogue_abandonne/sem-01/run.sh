#!/usr/bin/env bash
set -euo pipefail
POC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$POC_DIR/../.." && pwd)"
export PATH="$ROOT/.local/bin:$PATH"
exec "$ROOT/.venv-semiotic/bin/python" "$POC_DIR/run.py"
