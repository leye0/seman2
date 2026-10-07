#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/activate_local.sh
exec python poc/gen-02/run.py
