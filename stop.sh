#!/usr/bin/env bash
# MedRack — stop services started by run.sh.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
stopped=0
for svc in api frontend bot dashboard; do
  if [ -f ".run/$svc.pid" ]; then
    PID="$(cat ".run/$svc.pid")"
    if kill "$PID" 2>/dev/null; then echo "==> stopped $svc (pid $PID)"; stopped=1; fi
    rm -f ".run/$svc.pid"
  fi
done
[ "$stopped" = 0 ] && echo "==> nothing was running"
exit 0
