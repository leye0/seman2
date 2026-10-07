#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source scripts/activate_local.sh
exec python poc/x-01/run.py
