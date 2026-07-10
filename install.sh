#!/usr/bin/env bash
# MedRack — native installer for Ubuntu/Debian.
# Installs system deps, the Python backend (venv), and builds the frontend.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo "============================================"
echo "  MedRack installer"
echo "============================================"

# --- 1. System packages (tesseract = OCR, poppler = PDF rendering) ----------
if command -v apt-get >/dev/null 2>&1; then
  echo "==> Installing system packages (needs sudo): python3, venv, tesseract, poppler"
  sudo apt-get update -y
  sudo apt-get install -y python3 python3-venv python3-pip tesseract-ocr poppler-utils
else
  echo "WARN: apt-get not found. Ensure these are installed: python3 python3-venv tesseract-ocr poppler-utils"
fi

# --- 2. Toolchain checks ----------------------------------------------------
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null || { echo "ERROR: python3 not found"; exit 1; }
command -v node     >/dev/null || { echo "ERROR: node not found — install Node 20+ from https://nodejs.org"; exit 1; }
command -v npm      >/dev/null || { echo "ERROR: npm not found — install Node 20+ (bundles npm)"; exit 1; }
echo "==> Using $($PYTHON --version), node $(node --version), npm $(npm --version)"

# --- 3. .env ----------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> Created .env from .env.example"
fi
set -a; . ./.env; set +a
: "${MEDRACK_HOME:=$HOME/.medrack}"
: "${MEDRACK_API_BASE:=http://localhost:8000/api/v1}"

# --- 4. Backend: venv + install ---------------------------------------------
echo "==> Creating Python venv (.venv) and installing the backend"
echo "    (this downloads PyTorch/ChromaDB — a few minutes, ~2 GB, one time)"
"$PYTHON" -m venv .venv
./.venv/bin/pip install --upgrade pip wheel
./.venv/bin/pip install ./backend

# --- 5. Initialise data directories -----------------------------------------
echo "==> Initialising MedRack data dirs at: $MEDRACK_HOME"
MEDRACK_HOME="$MEDRACK_HOME" ./.venv/bin/medrack init || true

# --- 6. Frontend: install + build (Node server) -----------------------------
echo "==> Building the frontend (API base baked in: $MEDRACK_API_BASE)"
( cd frontend
  npm ci 2>/dev/null || npm install
  NITRO_PRESET=node-server VITE_MEDRACK_API_BASE="$MEDRACK_API_BASE" npm run build
)

echo
echo "============================================"
echo "  Install complete."
echo "  1. Edit .env and set OPENCODE_ZEN_API_KEY (real LLM mode)."
echo "  2. Start everything:   ./run.sh"
echo "  3. Stop everything:    ./stop.sh"
echo "============================================"
