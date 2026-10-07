#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(cd "$P/../.." && pwd)"
export PATH="$R/.local/bin:$PATH"
exec "$R/.venv-semiotic/bin/python" "$P/run.py"
