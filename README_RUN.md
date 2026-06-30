# MedRack Runbook

This is the **operator entry point** for the complete MedRack
application. After cloning, follow this document to get the
backend, frontend, dashboard, and bot running on any
Linux machine.

> If you only want to use MedRack (not develop it), use
> `start_medrack.sh` and `stop_medrack.sh` in this directory.
> If you want to develop or audit it, read the rest of this
> document.

---

## TL;DR

```bash
# 1. Clone the backend and frontend
git clone <your-medrack-backend-url>.git ~/.hermes/medrack
git clone <your-medrack-frontend-url>.git ~/medrack-frontend

# 2. Install system dependencies
sudo apt install -y tesseract-ocr poppler-utils

# 3. Install Python deps
python3.11 -m venv ~/.hermes/medrack/.venv
source ~/.hermes/medrack/.venv/bin/activate
pip install -e ~/.hermes/medrack

# 4. Configure env
cat > ~/.hermes/medrack/.env <<EOF
MEDRACK_HOME=$HOME/.hermes/medrack
MEDRACK_LLM_MODE=mock
# OPENCODE_ZEN_API_KEY=***  # required for real LLM
# MEDRACK_TELEGRAM_BOT_TOKEN=***  # required for bot
# MEDRACK_OPERATOR_CHAT_ID=***   # required for bot
EOF
export $(cat ~/.hermes/medrack/.env | xargs)

# 5. Start everything
~/.hermes/medrack/start_medrack.sh
cd ~/medrack-frontend
npm install
echo "VITE_MEDRACK_API_BASE=http://localhost:8000/api/v1" > .env
npm run dev
```

Then open:
- **Frontend**: http://localhost:5173
- **Dashboard**: http://localhost:7860
- **API**: http://localhost:8000/api/v1

To stop:
```bash
~/.hermes/medrack/stop_medrack.sh
# Frontend: Ctrl-C in the terminal where `npm run dev` runs
```

---

## Architecture (what you're starting)

```
┌──────────────────────────────────────────────────────────────┐
│  Browser (the user)                                            │
│  ├── http://localhost:5173  — Frontend (Vite + React 19)     │
│  └── http://localhost:7860  — Gradio Dashboard (Python)      │
│                                                                │
│  Both talk to the API v1:                                       │
│  └── http://localhost:8000/api/v1 — FastAPI (Python)            │
│         │                                                      │
│         │ (uses)                                                │
│         ▼                                                      │
│  ┌────────────────────────────────────┐                       │
│  │  medrack/ Python package             │                       │
│  │  ├── LLM client (OpenCode Go API)  │  ←── real LLM (or mock)│
│  │  ├── Retrieval (ChromaDB)          │  ←── embedded, no server│
│  │  ├── Answer generation (reportlab) │  ←── generates PDFs   │
│  │  └── Validation (9 quality rules)  │                       │
│  └────────────────────────────────────┘                       │
│                                                                │
│  Optional: Telegram bot (separate long-poll process)         │
│  └── Reads $MEDRACK_TELEGRAM_BOT_TOKEN, $MEDRACK_OPERATOR_CHAT_ID
│                                                                │
│  No external services required. No Docker, no Redis, no Postgres.
│  ChromaDB is a Python library (runs in-process).              │
└──────────────────────────────────────────────────────────────┘
```

---

## 1. Prerequisites

### Hardware
- **CPU**: 2+ cores recommended (embedding model uses CPU by default)
- **RAM**: 8 GB minimum (4 GB for Python + 2 GB for embedding model + 2 GB for browser)
- **Disk**: 5 GB for the codebase, dependencies, and a small KB (~500 PDFs = 50 GB)

### OS
- **Linux** (Ubuntu 22.04+ recommended; the startup scripts use `bash`, `ss`, `pgrep`)
- macOS works with minor tweaks (replace `ss` with `lsof -i`)
- Windows requires WSL2

### Software
- **Python 3.11+** with `pip` and `venv`
- **Node.js 20+** with `npm` (or `bun` — the Lovable build uses bun, but `npm` works fine)
- **Tesseract 5+** for OCR of scanned PDFs:
  ```bash
  # Ubuntu / Debian
  sudo apt install -y tesseract-ocr
  # macOS
  brew install tesseract
  ```
- **Poppler** for PDF rendering:
  ```bash
  sudo apt install -y poppler-utils
  brew install poppler
  ```
- **Chromium / Chrome** (optional, only needed if you use the browser-base browser tool elsewhere in Hermes)

### Network
- **Outbound HTTPS** to `https://api.opencode.ai` (only for real LLM mode)
- **Telegram** (only for the bot)

---

## 2. Clone the repositories

```bash
# Backend: the Python package + frozen API v1 + benchmark suite
git clone <your-medrack-backend-url>.git ~/.hermes/medrack

# Frontend: the Lovable-built React app
git clone <your-medrack-frontend-url>.git ~/medrack-frontend

# Verify
ls ~/.hermes/medrack/medrack/__init__.py       # backend
ls ~/medrack-frontend/src/lib/api/client.ts    # frontend
```

The convention `~/.hermes/medrack` for the backend is the
default `MEDRACK_HOME`. You can use a different path; set
the `MEDRACK_HOME` env var accordingly.

---

## 3. Install system dependencies

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y \
  python3.11 python3.11-venv python3-pip \
  tesseract-ocr poppler-utils \
  nodejs npm

# Verify
python3.11 --version
node --version
tesseract --version | head -1
```

---

## 4. Install the Python backend

```bash
# Create the venv (separate from any existing Hermes venv)
python3.11 -m venv ~/.hermes/medrack/.venv
source ~/.hermes/medrack/.venv/bin/activate

# Install medrack + all runtime deps
pip install -e ~/.hermes/medrack

# Verify
python -c "import medrack; print(medrack.__version__)"
# Expected: 0.3.0-backend-freeze
```

If `pip install` fails on a specific package (e.g. `pypdf` needs
system `gcc`), install the dev tools:
```bash
sudo apt install -y build-essential python3.11-dev
```

The first run will download the embedding model
(`all-MiniLM-L6-v2`, ~90 MB) into `~/.cache/huggingface/`. This
takes 1-2 minutes. Subsequent runs are instant.

---

## 5. Configure environment variables

Create `~/.hermes/medrack/.env`:

```bash
# Required: where the data lives
MEDRACK_HOME=$HOME/.hermes/medrack

# Required: LLM mode. Set to "mock" for offline / no API key.
# Set to "real" (or unset) for production with OpenCode Go.
MEDRACK_LLM_MODE=mock

# Required (for real mode only): your OpenCode Go API key
# OPENCODE_ZEN_API_KEY=***

# Optional: Telegram bot
# MEDRACK_TELEGRAM_BOT_TOKEN=***
# MEDRACK_OPERATOR_CHAT_ID=123456789
```

Load the env in your shell:
```bash
export $(cat ~/.hermes/medrack/.env | grep -v '^#' | xargs)
```

Or use a tool like `direnv` to auto-load it when you `cd` into
the directory.

### What each env var does

| Var | Required | Default | Purpose |
|---|---|---|---|
| `MEDRACK_HOME` | no | `~/.hermes/medrack` | Data root: books, modules, answers, ChromaDB |
| `MEDRACK_LLM_MODE` | no | `real` | `mock` uses `MockLLMClient` (no network, no key needed) |
| `OPENCODE_ZEN_API_KEY` | for real LLM | — | OpenCode Go API key (`x-api-key` header) |
| `MEDRACK_TELEGRAM_BOT_TOKEN` | for bot | — | Telegram bot token (from @BotFather) |
| `MEDRACK_OPERATOR_CHAT_ID` | for bot | — | Operator's Telegram chat ID (only this ID can issue operator commands) |

---

## 6. Initialize the data directories

```bash
source ~/.hermes/medrack/.venv/bin/activate
medrack init
```

This creates:
- `~/.hermes/medrack/books/` — drop KB textbook PDFs here
- `~/.hermes/medrack/modules/` — drop question-bank module PDFs here
- `~/.hermes/medrack/inbox/` — temporary ingest staging
- `~/.hermes/medrack/index/` — ChromaDB persistent store
- `~/.hermes/medrack/answers/` — generated answers (canonical cache)
- `~/.hermes/medrack/output/` — generated PDFs and zipped batches
- `~/.hermes/medrack/logs/` — backend logs
- `~/.hermes/medrack/state/` — runtime state files

It also writes an empty `manifest.json` (book + module inventory).

**No content is included in the clone.** You must add your own
KB textbooks and question banks to use MedRack meaningfully.

---

## 7. Start the stack

The simplest path — one command:

```bash
~/.hermes/medrack/start_medrack.sh
```

This starts:
1. **API v1** on `http://localhost:8000/api/v1` (the frontend's backend)
2. **Gradio dashboard** on `http://localhost:7860` (if not already running)
3. **Telegram bot** (if `MEDRACK_TELEGRAM_BOT_TOKEN` is set and not already running)

PIDs are written to `~/.hermes/medrack/.medrack/pids/`. Logs to
`~/.hermes/medrack/.medrack/logs/`.

### Start the frontend (separate process)

```bash
cd ~/medrack-frontend
npm install
echo "VITE_MEDRACK_API_BASE=http://localhost:8000/api/v1" > .env
npm run dev
```

The frontend dev server starts on `http://localhost:5173`. In
production, run `npm run build` and serve the `dist/` output
behind a reverse proxy.

### Ingest a KB textbook (one-time, per book)

```bash
source ~/.hermes/medrack/.venv/bin/activate
medrack ingest-book /path/to/kbook.pdf --subject psm
```

This runs the full T1-T9 pipeline: format detect → OCR (if
scanned) → chunk → embed → store in ChromaDB. A 500-page
textbook takes 5-10 minutes on CPU.

### Ingest a question-bank module (one-time, per module)

```bash
medrack ingest-module /path/to/qbmodule.pdf --subject psm --name "PSM-Module-1"
```

This runs M1-M5: extract → classify sections → store questions
for benchmarking.

### Generate an answer (the preview-approve workflow)

```bash
medrack preview --module psm-module-1 --chapter "Diabetes" --qid q001
medrack approve q001
medrack revise q001 --feedback "expand the management section"
medrack cancel
```

The full preview → approve → PDF flow is in `medrack/cli.py`.

### Run the benchmark suite

```bash
python -m medrack.benchmarks.run --llm mock --output-dir benchmarks/runs/$(date +%Y%m%d)
```

This is the canonical Phase 5 regression test: 20 questions,
12,000 tokens, 0.5 cache hit, ~3 seconds total.

---

## 8. Verification: the four key URLs

After `start_medrack.sh`, run these to confirm everything works:

```bash
# 1. API health
curl http://localhost:8000/api/v1/version
# Expected: {"schema_version":1,"package_version":"0.3.0-backend-freeze",...}

# 2. Library (after ingesting at least one book)
curl http://localhost:8000/api/v1/library/books
# Expected: [...]

# 3. Pipeline inspection
curl "http://localhost:8000/api/v1/pipeline/inspect?qid=q001&question_text=What+is+diabetes&subject=psm&marks=5"
# Expected: {"schema_version":1,"qid":"q001","stages":[...],"total_latency_seconds":...}

# 4. Frontend reachable
curl -I http://localhost:5173/  # (in another terminal, after `npm run dev`)
# Expected: HTTP/1.1 200 OK
```

If any of these fail, see the **Troubleshooting** section below.

---

## 9. The startup scripts in detail

### `start_medrack.sh`

What it does (in order):

1. **Resolve paths**: `MEDRACK_HOME` (default `~/.hermes/medrack`),
   `MEDRACK_VENV` (default `~/.hermes/hermes-agent/venv` — the
   existing Hermes venv, since medrack is installed there in
   this deployment)
2. **Validate the environment**: medrack package exists, venv
   python exists
3. **Run `medrack init`**: idempotent — creates dirs if missing
4. **Start API v1** (FastAPI, port 8000) via uvicorn, if not
   already running. Waits up to 10s for the port to come up.
5. **Start dashboard** (Gradio, port 7860) via `medrack cli dashboard`,
   if not already running. Skipped if port 7860 is already bound
   (e.g. by the systemd service).
6. **Start Telegram bot** via `medrack cli bot`, if
   `MEDRACK_TELEGRAM_BOT_TOKEN` is set and not already running.
   Skipped if `pgrep -f "medrack bot"` finds a running instance.

Idempotent: re-running is safe; existing services are reused.

### `stop_medrack.sh`

Stops only the processes we started (tracked in
`~/.hermes/medrack/.medrack/pids/`). Does NOT touch
systemd-managed services. Use `--force` to kill any
remaining medrack processes by name.

```bash
~/.hermes/medrack/stop_medrack.sh
~/.hermes/medrack/stop_medrack.sh --force   # also kill systemd-managed
```

---

## 10. Production deployment (optional)

For a non-developer deployment, the systemd unit templates
(in `medrack-dashboard.service`, `medrack-bot.service`)
can be installed:

```bash
# As the user that will own the services:
mkdir -p ~/.config/systemd/user
cp ~/.hermes/medrack/docs/operations/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now medrack-dashboard.service
systemctl --user enable --now medrack-bot.service
loginctl enable-linger  # so the user services survive logout
```

To add the API v1 to systemd (currently only dashboard + bot are
managed there):

```ini
# ~/.config/systemd/user/medrack-api.service
[Unit]
Description=MedRack API v1 (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/YOU/.hermes/medrack
EnvironmentFile=/home/YOU/.hermes/medrack/.env
ExecStart=/home/YOU/.hermes/hermes-agent/venv/bin/python -m uvicorn medrack.dashboard.api.v1:app --host 0.0.0.0 --port 8000 --log-level info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

---

## 11. Troubleshooting

### "API v1 did not bind port 8000 within 10s"

Check the log:
```bash
cat ~/.hermes/medrack/.medrack/logs/api.log
```

Common causes:
- Another process is on port 8000: `sudo ss -tlnp | grep 8000`
- A previous start_medrack.sh crashed: `~/.hermes/medrack/stop_medrack.sh --force`

### "medrack init failed"

Usually a permission issue. Check:
```bash
ls -ld ~/.hermes/medrack/
```

If you set `MEDRACK_HOME` to a path owned by another user, that's
the bug. Fix the ownership or unset `MEDRACK_HOME` to use the
default.

### "Frontend can't reach backend"

The frontend uses `VITE_MEDRACK_API_BASE` (build-time env var).
After changing it, you MUST restart `npm run dev` (or rebuild).

### Generation returns `ok: false` with "Unknown question type: None"

**This is a known bug in the API v1 endpoint**, not a setup
issue. The `medrack dashboard services questions generate` method
does not propagate the `question_type` field to the question
dict that `medrack answer generate` expects. The CLI path
(`medrack preview && medrack approve`) is unaffected and works
end-to-end. To work around the API bug, set the `type` field
in the request body explicitly:

```bash
curl -X POST http://localhost:8000/api/v1/questions/generate \
  -H "Content-Type: application/json" \
  -d '{"qid":"smoke","question_text":"What is diabetes?","subject":"psm","marks":5,"question_type":"theory"}'
```

(The `question_type` field IS accepted by the API; the bug is
that the dashboard service doesn't pass it through to
`generate_answer`. This is tracked as a known issue — do not
report it as new.)

### Embedding model download is slow or fails

The first run downloads `all-MiniLM-L6-v2` (~90 MB) from
HuggingFace. If you're behind a firewall or want to pre-cache:

```bash
source ~/.hermes/medrack/.venv/bin/activate
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```

If HuggingFace is unreachable, set `HF_HUB_OFFLINE=1` after
pre-caching, or use a local mirror.

### "Bot is not responding"

Check that the operator chat ID matches your real Telegram chat:
```bash
echo "Your MEDRACK_OPERATOR_CHAT_ID: $MEDRACK_OPERATOR_CHAT_ID"
# In Telegram, message @userinfobot to get your chat ID
```

The bot silently ignores messages from other chat IDs (security
feature — operator-only commands).

### "medrack command not found"

The `medrack` command is installed by `pip install -e` into
your venv. Activate the venv first:
```bash
source ~/.hermes/medrack/.venv/bin/activate  # or wherever your venv is
which medrack
# Expected: /path/to/venv/bin/medrack
```

### "PDF generation works in benchmark but not in dashboard"

See the "Unknown question type" bug above. The CLI path is fine.

---

## 12. What is NOT included in the start scripts

For the sake of clarity, these are intentionally NOT auto-started
by `start_medrack.sh`:

- **The frontend dev server**. It's a Node process, not a
  Python service, and the operator typically runs it in their
  own terminal with hot-reload. Use `cd ~/medrack-frontend && npm run dev`.
- **PDF generation commands**. These are user-driven
  (`medrack preview && medrack approve`), not background services.
- **The benchmark suite**. Run on demand, not as a service.
- **OCR ingestion**. Run on demand (`medrack ingest-book`).
- **Docker / docker-compose**. The deployment is intentionally
  script-based, not containerized, to keep the entry point
  minimal. If you need containerization, see `docs/operations/docker.md`
  (TODO).

---

## 13. File / directory reference

```
~/.hermes/medrack/                  ← MEDRACK_HOME (default)
├── medrack/                        ← the Python package (source)
├── books/                          ← KB textbook PDFs (you add)
├── modules/                        ← question-bank module PDFs
├── inbox/                          ← ingest staging area
├── index/                          ← ChromaDB persistent store
│   └── chroma/                     ← vector index files
├── answers/                        ← generated answers (cache)
├── output/                         ← PDFs and zipped batches
├── logs/                           ← application logs
│   └── medrack-bot.log
│   └── medrack-dashboard.log
├── state/                          ← runtime state (llm_mode, etc.)
├── benchmarks/                     ← benchmark runs
├── .medrack/                       ← runtime state (created by start_medrack.sh)
│   ├── pids/                       ← PID files
│   └── logs/                       ← startup script logs
├── docs/                           ← all documentation
├── start_medrack.sh                ← this runbook's entry script
├── stop_medrack.sh                 ← and its counterpart
├── README_RUN.md                   ← this file
├── pyproject.toml                  ← Python project metadata
└── medrack.egg-info/               ← pip metadata
```

```
~/medrack-frontend/                 ← the Lovable frontend
├── src/
│   ├── components/                 ← React components
│   ├── routes/                     ← TanStack Start file-based routes
│   ├── lib/api/                    ← API client (http + mock)
│   └── styles.css
├── docs/frontend/                  ← integration handoff docs
├── .env                            ← VITE_MEDRACK_API_BASE
└── package.json
```

---

## 14. Quick reference: all CLI commands

```bash
medrack init                                # create data dirs
medrack status                              # show deps + dirs
medrack version                             # print version
medrack ingest-book <pdf> --subject <s>     # ingest KB textbook
medrack ingest-module <pdf> --subject <s> --name <n>  # ingest module
medrack preview --module <m> --chapter <c> --qid <q>  # generate preview
medrack approve <q>                         # approve + render PDF
medrack revise <q> --feedback "<txt>"      # revise
medrack cancel                              # cancel preview
medrack dashboard                           # start Gradio dashboard
medrack bot                                 # start Telegram bot
medrack benchmark --llm mock                # run benchmark
python -m medrack.benchmarks.run ...        # same, more options
```

---

## 15. Support

If something is broken and the troubleshooting section doesn't
help, file an issue at the operator's issue tracker with:
- The output of `medrack status`
- The last 50 lines of `~/.hermes/medrack/.medrack/logs/api.log`
- The exact command and request that failed
- The output of `~/.hermes/hermes-agent/venv/bin/python --version`
- The output of `node --version` and `tesseract --version`

The audit is intentionally minimal — the goal is "a new
developer clones and runs in under 30 minutes" not "a new
developer understands the entire system". For the latter, see
`docs/architecture/0013-backend-freeze.md` and the rest of
`docs/architecture/`.
