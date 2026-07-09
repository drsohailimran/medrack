#!/usr/bin/env bash
set -uo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
set -a
source "$ROOT/.env"
set +a
export MEDRACK_HOME="${MEDRACK_HOME:-/home/sohail/medrack-data}"
export PATH="$ROOT/.venv/bin:$PATH"
cd "$ROOT"
mkdir -p "$MEDRACK_HOME/logs" "$ROOT/.run" "$MEDRACK_HOME/.medrack/pids"
API_PORT="${API_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-3010}"

if ! ss -tln | grep -q ":${API_PORT} "; then
  nohup env MEDRACK_HOME="$MEDRACK_HOME" "$ROOT/.venv/bin/python" -m uvicorn medrack.dashboard.api.v1:app \
    --host 0.0.0.0 --port "$API_PORT" \
    > "$MEDRACK_HOME/logs/api.log" 2>&1 &
  echo $! > "$ROOT/.run/api.pid"
  echo "API :$API_PORT pid $(cat $ROOT/.run/api.pid)"
else
  echo "API already :$API_PORT"
fi

if [ -f "$ROOT/frontend/.output/server/index.mjs" ]; then
  if ! ss -tln | grep -q ":${FRONTEND_PORT} "; then
    cd "$ROOT/frontend"
    nohup env PORT="$FRONTEND_PORT" node .output/server/index.mjs \
      > "$MEDRACK_HOME/logs/frontend.log" 2>&1 &
    echo $! > "$ROOT/.run/frontend.pid"
    cd "$ROOT"
    echo "Frontend :$FRONTEND_PORT"
  else
    echo "Frontend already :$FRONTEND_PORT"
  fi
fi

if ! ss -tln | grep -q ":7860 "; then
  nohup env MEDRACK_HOME="$MEDRACK_HOME" "$ROOT/.venv/bin/medrack" dashboard \
    > "$MEDRACK_HOME/logs/dashboard.log" 2>&1 &
  echo $! > "$ROOT/.run/dashboard.pid"
  echo "Dashboard :7860"
fi
sleep 2
ss -tln | grep -E ':8010 |:3010 |:7860 ' || true
curl -sS "http://127.0.0.1:${API_PORT}/api/v1/version" || true
echo
