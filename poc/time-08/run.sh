#!/usr/bin/env bash
set -euo pipefail
POC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$POC_DIR/../.." && pwd)"
exec "$ROOT/.venv/bin/python" "$POC_DIR/run.py"
