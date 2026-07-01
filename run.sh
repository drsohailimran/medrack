#!/usr/bin/env bash
# MedRack — start the API + frontend (and the Telegram bot if a token is set).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

[ -f .env ] && { set -a; . ./.env; set +a; }
: "${MEDRACK_HOME:=$HOME/medrack-data}"
: "${API_PORT:=8010}"
: "${FRONTEND_PORT:=3010}"
export MEDRACK_HOME

if [ ! -x .venv/bin/python ]; then echo "ERROR: backend not installed — run ./install.sh first"; exit 1; fi
if [ ! -f frontend/.output/server/index.mjs ]; then echo "ERROR: frontend not built — run ./install.sh first"; exit 1; fi

mkdir -p .run
is_running() { [ -f ".run/$1.pid" ] && kill -0 "$(cat ".run/$1.pid")" 2>/dev/null; }

start() { # name, logfile, command...
  local name="$1" log="$2"; shift 2
  if is_running "$name"; then echo "==> $name already running (pid $(cat ".run/$name.pid"))"; return; fi
  echo "==> Starting $name"
  setsid "$@" > ".run/$log" 2>&1 < /dev/null &
  echo $! > ".run/$name.pid"
}

# API (FastAPI / uvicorn)
start api api.log ./.venv/bin/python -m uvicorn medrack.dashboard.api.v1:app --host 0.0.0.0 --port "$API_PORT"

# Frontend (Nitro node server; PORT is read by the node server)
if is_running frontend; then
  echo "==> frontend already running (pid $(cat .run/frontend.pid))"
else
  echo "==> Starting frontend"
  ( cd frontend && PORT="$FRONTEND_PORT" setsid node .output/server/index.mjs > "$HERE/.run/frontend.log" 2>&1 < /dev/null & echo $! > "$HERE/.run/frontend.pid" )
fi

# Telegram bot (optional — only if a token is configured)
if [ -n "${MEDRACK_TELEGRAM_BOT_TOKEN:-}" ]; then
  start bot bot.log ./.venv/bin/medrack bot
fi

sleep 2
echo
echo "MedRack is up:"
echo "  Frontend (UI):  http://localhost:$FRONTEND_PORT"
echo "  API:            http://localhost:$API_PORT/api/v1   (health: /version)"
echo "  API docs:       http://localhost:$API_PORT/docs"
echo
echo "Logs: .run/api.log, .run/frontend.log     Stop: ./stop.sh"
