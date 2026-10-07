#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
exec .venv/bin/python poc/ind-05/run.py
