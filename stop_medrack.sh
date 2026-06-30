#!/usr/bin/env bash
# Stop the MedRack application stack started by start_medrack.sh.
#
# This script:
#   1. Stops the API v1 (FastAPI) by killing the recorded PID.
#   2. Stops the Gradio dashboard, but only if we started it
#      (i.e. the PID file exists). If the dashboard is running
#      as a systemd service (medrack-dashboard.service), it
#      leaves it alone.
#   3. Stops the Telegram bot, with the same systemd-service
#      caveat.
#
# Usage:
#   ./stop_medrack.sh
#   ./stop_medrack.sh --force   # also kill any system-wide medrack processes

set -euo pipefail

MEDRACK_HOME="${MEDRACK_HOME:-$HOME/.hermes/medrack}"
RUNTIME_DIR="$MEDRACK_HOME/.medrack/pids"
LOG_DIR="$MEDRACK_HOME/.medrack/logs"
API_PORT="${API_PORT:-8000}"
DASH_PORT="${DASH_PORT:-7860}"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

stop_pid() {
  local name="$1"
  local pidfile="$RUNTIME_DIR/${name}.pid"
  if [[ ! -f "$pidfile" ]]; then
    log "$name: no pid file (not started by us)"
    return 0
  fi
  local pid
  pid="$(cat "$pidfile")"
  if ! kill -0 "$pid" 2>/dev/null; then
    log "$name: pid $pid not alive, cleaning up"
    rm -f "$pidfile"
    return 0
  fi
  log "$name: stopping pid $pid (SIGTERM)..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
    sleep 0.5
  done
  if kill -0 "$pid" 2>/dev/null; then
    log "$name: still alive, sending SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
  log "$name: stopped"
}

log "Stopping MedRack stack..."

stop_pid api
stop_pid dashboard
stop_pid bot

if [[ "$FORCE" == "1" ]]; then
  log "Force mode: killing any remaining medrack processes..."
  pkill -f "medrack bot" 2>/dev/null || true
  pkill -f "medrack dashboard" 2>/dev/null || true
  pkill -f "medrack.dashboard.api" 2>/dev/null || true
fi

log "Done."
