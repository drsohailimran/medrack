> **SINGLE WORKSPACE:** This directory (`/home/sohail/medrack`) is the only app tree.
> Data lives in `/home/sohail/medrack-data`. See `MEDRACK_CANONICAL.md` and `docs/MEDRACK_FULL_SYSTEM_HANDOFF.md`.
> Archive of old copies: `/home/sohail/medrack-ARCHIVE-20260709` (do not use).

# MedRack — Ubuntu deployment bundle

A local RAG system for MBBS theory-exam answer generation: a FastAPI backend
(+ Gradio operator dashboard + optional Telegram bot) and a React/TanStack
frontend.

This bundle installs and runs the whole stack natively on Ubuntu/Debian.

## Prerequisites

- **Ubuntu/Debian** (uses `apt-get`; tested target: 22.04+)
- **Node.js 20+** and npm — https://nodejs.org (the installer does NOT install Node)
- Internet access on first install (downloads Python deps incl. PyTorch ~2 GB,
  npm packages, and a ~90 MB embedding model on first generation)
- `sudo` access (to apt-install `tesseract-ocr` and `poppler-utils`)

Python 3.10+ (3.11 recommended), tesseract, and poppler are installed for you
by `install.sh` via apt.

## Quick start

```bash
tar -xzf medrack-app.tar.gz
cd medrack-app

./install.sh                 # system deps + backend venv + frontend build

nano .env                    # set OPENCODE_ZEN_API_KEY (real LLM mode)

./run.sh                     # start API + frontend
```

Then open:

- **Frontend (UI):** http://localhost:3000
- **API:**          http://localhost:8000/api/v1  (health check: `/version`)
- **API docs:**     http://localhost:8000/docs

Stop everything with `./stop.sh`.

## LLM mode

This bundle defaults to **real** LLM mode (`MEDRACK_LLM_MODE=real` in `.env`),
which needs an `OPENCODE_ZEN_API_KEY`. Until you set it, the app boots and the
UI works, but answer generation returns an error.

To try it **offline first**, set `MEDRACK_LLM_MODE=mock` in `.env` and restart
(`./stop.sh && ./run.sh`) — generation then returns deterministic stub answers,
no key required.

## Adding content (so generation has something to ground on)

No textbooks/question-banks ship with this bundle. Add your own:

```bash
source .venv/bin/activate
medrack ingest-book   /path/to/textbook.pdf      --subject psm
medrack ingest-module /path/to/module.pdf        --subject psm --name "PSM-Module-1"
```

You can also upload a question bank from the UI / API
(`POST /api/v1/library/question-banks/upload`).

## Accessing the UI from another device

The frontend bakes the API URL at build time. By default it is
`http://localhost:8000/api/v1`, which only works in a browser on the same
machine. To open the UI from another device on your LAN, edit `.env`:

```
MEDRACK_API_BASE=http://<this-machine-LAN-IP>:8000/api/v1
```

then re-run `./install.sh` (rebuilds the frontend) and `./run.sh`.
Both servers already listen on all interfaces (`0.0.0.0`).

## Optional: operator dashboard & Telegram bot

- **Gradio dashboard:** `./.venv/bin/medrack dashboard` → http://localhost:7860
- **Telegram bot:** set `MEDRACK_TELEGRAM_BOT_TOKEN` + `MEDRACK_OPERATOR_CHAT_ID`
  in `.env`; `run.sh` then starts it automatically.

## Layout

```
medrack-app/
  install.sh        # one-time setup (apt + venv + pip + npm build)
  run.sh            # start API + frontend (+ bot if configured)
  stop.sh           # stop them
  .env.example      # config template (copied to .env by install.sh)
  backend/          # the medrack Python package + pyproject
  frontend/         # the React/TanStack app (built to frontend/.output by install.sh)
  .run/             # pid files + logs (created by run.sh)
```

## Troubleshooting

- **`./install.sh: /bin/bash^M: bad interpreter`** — line endings got mangled.
  Fix: `sed -i 's/\r$//' install.sh run.sh stop.sh .env`.
- **Frontend can't reach backend** — the API base is baked at build time; after
  changing `MEDRACK_API_BASE`, re-run `./install.sh`.
- **API didn't start** — check `.run/api.log`. Port 8000 already in use? change
  `API_PORT` in `.env`.
- **Generation says LLM error** — set `OPENCODE_ZEN_API_KEY` (real mode) or use
  `MEDRACK_LLM_MODE=mock`.
- **Run the backend test suite:** `./.venv/bin/python -m pytest backend/medrack/tests`
  (some tests require sample PDFs + tesseract/poppler and are skipped/failed
  without that content — that's expected).
