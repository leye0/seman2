#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
exec .venv-dialogue/bin/python poc/dlg-05/run.py
