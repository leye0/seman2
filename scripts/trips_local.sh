#!/usr/bin/env bash
set -euo pipefail

SEMAN2_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$SEMAN2_ROOT/scripts/activate_local.sh"

port="${TRIPS_PORT:-6200}"
if [[ $# -gt 0 ]]; then
  port="$1"
fi
if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
  printf 'Port TRIPS invalide : %s\n' "$port" >&2
  exit 2
fi
if [[ ! -x "$TRIPS_BASE/bin/trips-cogent" ]]; then
  printf 'TRIPS local absent. Lancez ./scripts/seman2 install-trips\n' >&2
  exit 1
fi

log_dir="$SEMAN2_ROOT/.local/var/trips/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$log_dir"
exec "$TRIPS_BASE/bin/trips-cogent" \
  -nouser -nocsm -nochat -port "$port" -logdir "$log_dir"
