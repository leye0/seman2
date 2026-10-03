#!/usr/bin/env bash
set -euo pipefail

POC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$POC_DIR/../.." && pwd)"

"$REPO_ROOT/poc/time-01/run.sh"
"$REPO_ROOT/poc/time-02/run.sh"
exec "$REPO_ROOT/scripts/seman2" python "$POC_DIR/run.py" "$@"
