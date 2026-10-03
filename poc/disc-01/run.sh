#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; R="$(cd "$P/../.." && pwd)"

if [[ "${SEMAN2_RST_BOUNDED:-}" != "1" ]]; then
  command -v systemd-run >/dev/null || {
    printf 'DISC-01 refuse une execution RST non bornee: systemd-run est requis.\n' >&2
    exit 70
  }
  exec systemd-run --user --quiet --wait --collect --pipe \
    --setenv=SEMAN2_RST_BOUNDED=1 \
    --property=MemoryHigh=3G \
    --property=MemoryMax=3G \
    --property=MemorySwapMax=0 \
    --property=CPUQuota=100% \
    --property=TasksMax=128 \
    --property=Nice=10 \
    --property=RuntimeMaxSec=360 \
    --property=TimeoutStopSec=5 \
    --property=KillMode=control-group \
    "$P/run.sh"
fi

exec "$R/scripts/run_rst_parser.sh" "$P/run.py"
