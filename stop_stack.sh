#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
for f in api frontend dashboard bot; do
  if [ -f "$ROOT/.run/$f.pid" ]; then
    kill "$(cat "$ROOT/.run/$f.pid")" 2>/dev/null || true
    rm -f "$ROOT/.run/$f.pid"
  fi
done
for port in 8010 3010 7860 8000; do
  while read -r line; do
    pid=$(echo "$line" | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1)
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done < <(ss -tlnp 2>/dev/null | grep ":${port} " || true)
done
echo stopped
