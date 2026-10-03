#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")"&&pwd)";R="$(cd "$P/../.."&&pwd)";exec "$R/.venv-dialogue/bin/python" "$P/run.py"
