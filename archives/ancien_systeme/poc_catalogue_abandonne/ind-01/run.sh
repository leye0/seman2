#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
exec .venv/bin/python poc/ind-01/run.py
