#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(cd "$P/../.." && pwd)"
exec "$R/.venv-semiotic/bin/python" "$P/run.py"
