#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
exec .venv/bin/python poc/graph-03/run.py
