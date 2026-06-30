#!/usr/bin/env bash
# Start the complete MedRack application stack.
#
# This script launches:
#   1. The MedRack JSON API v1 (FastAPI, port 8000) — the frontend's
#      backend. This is the primary "operator entry point" that was
#      previously missing. The Gradio dashboard and Telegram bot
#      already have their own systemd services; this script will
#      reuse them if running, or start standalone fallbacks if not.
#   2. The Gradio dashboard (port 7860), if not already running.
#   3. The Telegram bot (long-poll), if $MEDRACK_TELEGRAM_BOT_TOKEN
#      is set and not already running.
#   4. (No ChromaDB process — chromadb is a Python library; the
#      server process is the medrack API process itself.)
#
# All PIDs are written to $MEDRACK_HOME/.medrack/pids/ so that
# stop_medrack.sh can find them.
#
# Usage:
#   ./start_medrack.sh
#   VITE_MEDRACK_API_BASE=http://10.0.0.5:8000/api/v1 ./start_medrack.sh
#   MEDRACK_LLM_MODE=mock ./start_medrack.sh  # offline / no API key
#
# See README_RUN.md for the full operator runbook.

set -euo pipefail

# ----- Resolve paths -----

# MEDRACK_HOME is the data root. Default: ~/.hermes/medrack.
# The repo *source* lives in MEDRACK_HOME/medrack/ (the package dir).
MEDRACK_HOME="${MEDRACK_HOME:-$HOME/.hermes/medrack}"
MEDRACK_PKG_DIR="$MEDRACK_HOME/medrack"
MEDRACK_VENV="${MEDRACK_VENV:-$HOME/.hermes/hermes-agent/venv}"
RUNTIME_DIR="$MEDRACK_HOME/.medrack/pids"
LOG_DIR="$MEDRACK_HOME/.medrack/logs"
mkdir -p "$RUNTIME_DIR" "$LOG_DIR"

# API port (the frontend's backend). Default 8000.
API_PORT="${API_PORT:-8000}"
# Dashboard port. Default 7860.
DASH_PORT="${DASH_PORT:-7860}"

# ----- Helpers -----

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

is_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
  else
    netstat -tln 2>/dev/null | awk '{print $4}' | grep -qE "[:.]${port}\$"
  fi
}

pid_alive() {
  local pidfile="$1"
  [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null
}

# ----- 1. Validate the environment -----

if [[ ! -d "$MEDRACK_PKG_DIR" ]]; then
  log "ERROR: medrack package not found at $MEDRACK_PKG_DIR"
  log "  Set MEDRACK_HOME to the directory containing the medrack/ source tree."
  exit 1
fi

if [[ ! -x "$MEDRACK_VENV/bin/python" ]]; then
  log "ERROR: venv python not found at $MEDRACK_VENV/bin/python"
  log "  Set MEDRACK_VENV to the directory of the venv with medrack + deps installed."
  exit 1
fi

PY="$MEDRACK_VENV/bin/python"
log "medrack package: $MEDRACK_PKG_DIR"
log "venv python:     $MEDRACK_VENV"
log "MEDRACK_HOME:     $MEDRACK_HOME"
log "LLM mode:        ${MEDRACK_LLM_MODE:-real}"

# ----- 2. Initialize data dirs (idempotent) -----

log "Initializing medrack data directories..."
"$PY" -m medrack.cli init >"$LOG_DIR/init.log" 2>&1 || {
  log "WARNING: medrack init failed (see $LOG_DIR/init.log). Continuing..."
}

# ----- 3. Start the API v1 (FastAPI on $API_PORT) -----

API_PID="$RUNTIME_DIR/api.pid"
API_LOG="$LOG_DIR/api.log"

if pid_alive "$API_PID"; then
  log "API v1 already running (pid $(cat "$API_PID")), reusing"
elif is_listening "$API_PORT"; then
  log "API v1 port $API_PORT already bound by another process, reusing"
else
  log "Starting API v1 on port $API_PORT..."
  cd "$MEDRACK_PKG_DIR"

  # Load the .env file (if present) so OPENCODE_ZEN_API_KEY and
  # other secrets reach the API process. The file is mode 600,
  # owned by the operator. We source it into the uvicorn env.
  if [[ -f "$MEDRACK_HOME/.env" ]]; then
    log "Loading env from $MEDRACK_HOME/.env"
    set -a
    # shellcheck disable=SC1090
    source "$MEDRACK_HOME/.env"
    set +a
  fi

  nohup "$PY" -m uvicorn medrack.dashboard.api.v1:app \
    --host 0.0.0.0 --port "$API_PORT" --log-level info \
    >"$API_LOG" 2>&1 &
  echo $! > "$API_PID"
  log "API v1 pid: $(cat "$API_PID"), log: $API_LOG"
  # Wait for the port to come up (max 10s)
  for _ in $(seq 1 20); do
    if is_listening "$API_PORT"; then break; fi
    sleep 0.5
  done
  if ! is_listening "$API_PORT"; then
    log "WARNING: API v1 did not bind port $API_PORT within 10s (check $API_LOG)"
  else
    log "API v1 listening on http://0.0.0.0:$API_PORT"
  fi
fi

# ----- 4. Start the Gradio dashboard (if not already running) -----

DASH_PID="$RUNTIME_DIR/dashboard.pid"
DASH_LOG="$LOG_DIR/dashboard.log"

if pid_alive "$DASH_PID"; then
  log "Dashboard already running (pid $(cat "$DASH_PID")), reusing"
elif is_listening "$DASH_PORT"; then
  log "Dashboard port $DASH_PORT already bound (likely systemd service), reusing"
else
  log "Starting Gradio dashboard on port $DASH_PORT..."
  cd "$MEDRACK_PKG_DIR"
  nohup "$PY" -m medrack.cli dashboard >"$DASH_LOG" 2>&1 &
  echo $! > "$DASH_PID"
  log "Dashboard pid: $(cat "$DASH_PID"), log: $DASH_LOG"
  for _ in $(seq 1 20); do
    if is_listening "$DASH_PORT"; then break; fi
    sleep 0.5
  done
  if ! is_listening "$DASH_PORT"; then
    log "WARNING: Dashboard did not bind port $DASH_PORT within 10s (check $DASH_LOG)"
  else
    log "Dashboard listening on http://0.0.0.0:$DASH_PORT"
  fi
fi

# ----- 5. Start the Telegram bot (if token set and not already running) -----

BOT_PID="$RUNTIME_DIR/bot.pid"
BOT_LOG="$LOG_DIR/bot.log"

if [[ -n "${MEDRACK_TELEGRAM_BOT_TOKEN:-}" ]]; then
  if pid_alive "$BOT_PID"; then
    log "Bot already running (pid $(cat "$BOT_PID")), reusing"
  elif pgrep -f "medrack bot" >/dev/null 2>&1; then
    log "Bot already running as systemd service, reusing"
  else
    log "Starting Telegram bot (foreground log: $BOT_LOG)..."
    cd "$MEDRACK_PKG_DIR"
    nohup "$PY" -m medrack.cli bot >"$BOT_LOG" 2>&1 &
    echo $! > "$BOT_PID"
    log "Bot pid: $(cat "$BOT_PID")"
  fi
else
  log "MEDRACK_TELEGRAM_BOT_TOKEN not set; skipping bot"
fi

# ----- 6. Summary -----

cat <<EOF

================================================================
  MedRack is up.
================================================================
  API v1:      http://localhost:${API_PORT}/api/v1
  Dashboard:   http://localhost:${DASH_PORT}
  Health:      curl http://localhost:${API_PORT}/api/v1/version
  Stop:        ./stop_medrack.sh
  Logs:        $LOG_DIR/
  PIDs:        $RUNTIME_DIR/
================================================================

EOF
