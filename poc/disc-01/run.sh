#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(cd "$P/../.." && pwd)"
exec "$R/scripts/run_rst_parser.sh" "$P/run.py"
