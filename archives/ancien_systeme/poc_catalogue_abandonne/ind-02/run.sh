#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/activate_local.sh
exec .venv-popper/bin/python poc/ind-02/run.py
