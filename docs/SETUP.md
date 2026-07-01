# Setup

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Python 3.11+** | Backend runtime |
| **Node 20+** (with npm) | Frontend build/serve |
| **System packages** | `tesseract-ocr` (OCR), `poppler-utils` (PDF), `graphviz` (flowcharts) — installed automatically by `install.sh` on Debian/Ubuntu |
| **An LLM** | Either a Google Gemini API key (free) **or** a machine that can run a local model — see [Running a local model](#running-a-local-model) |

Hardware: the backend, ChromaDB, and embeddings run comfortably on a normal
server/desktop (no GPU needed for MedRack itself). A GPU is only needed if you
run a **local** LLM.

---

## Install on Ubuntu (production)

```bash
git clone <your-repo-url> medrack
cd medrack
bash install.sh
```

`install.sh` will:
1. `apt-get install` the system packages,
2. create a Python venv (`.venv`) and `pip install ./backend` (downloads
   PyTorch/ChromaDB — a few minutes, ~2 GB, one time),
3. run `medrack init` to create the data directories under `MEDRACK_HOME`,
4. `npm ci` and build the frontend (Nitro node-server).

Then configure your LLM and start:

```bash
nano .env       # pick Gemini or a local model (see CONFIGURATION.md)
bash run.sh     # UI: http://localhost:3010   API: http://localhost:8010
bash stop.sh    # stop everything
```

---

## Running a local model

MedRack talks to any **OpenAI-compatible** server via the `llamacpp` provider,
so you can run a local model with [llama.cpp](https://github.com/ggml-org/llama.cpp).
The model can run on the same box or on a **separate GPU machine on your LAN**
(e.g. a Windows PC with an RTX 3060 Ti — the setup this project was built on).

### 1. Start a llama.cpp server

Example for **Qwen/Qwopus 30B-A3B** (a Mixture-of-Experts model) on an 8 GB GPU.
The key trick is `--n-cpu-moe`, which keeps the MoE expert tensors on the CPU
and the attention layers on the GPU, so a 30B MoE fits in 8 GB VRAM:

```bash
llama-server \
  --model /path/to/Qwopus3.6-35B-A3B-Q4_K_M.gguf \
  --n-cpu-moe 32 \        # offload MoE experts to CPU (tune 28-34 for your VRAM)
  --n-gpu-layers 999 \    # attention/other layers on GPU
  --ctx-size 16384 \
  --flash-attn on \
  --jinja \               # enable the chat template
  --host 0.0.0.0 \        # listen on the LAN
  --port 8080
```

Tuning notes:
- Higher `--n-cpu-moe` → less VRAM used, slightly slower. Lower → more VRAM,
  faster, until you run out. On an 8 GB 3060 Ti, `32` gave ~38 tok/s.
- `--host 0.0.0.0` lets another machine (the MedRack box) reach it over the LAN.

### 2. Point MedRack at it

In `.env`:
```bash
MEDRACK_LLM_PROVIDER=llamacpp
MEDRACK_LLM_MODEL=qwopus
MEDRACK_LLM_BASE_URL=http://<gpu-machine-ip>:8080   # or localhost if same box
MEDRACK_LLM_TIMEOUT=600
```

Restart MedRack (`bash stop.sh && bash run.sh`). That's it.

> Prefer **Ollama**? Set `MEDRACK_LLM_PROVIDER=ollama` and
> `MEDRACK_LLM_BASE_URL=http://<host>:11434`. Ollama is simpler but lacks the
> `--n-cpu-moe` offload, so large MoE models need more VRAM.

---

## Accessing the UI from another device

The frontend bakes the API URL in at **build time**. To open the UI from a phone
or another PC on the LAN:

1. Set `MEDRACK_API_BASE=http://<server-lan-ip>:8010/api/v1` in `.env`.
2. Rebuild the frontend:
   ```bash
   cd frontend
   NITRO_PRESET=node-server VITE_MEDRACK_API_BASE="$MEDRACK_API_BASE" npm run build
   cd .. && bash stop.sh && bash run.sh
   ```
3. Browse to `http://<server-lan-ip>:3010`.

---

## Development setup

### Backend (editable install for fast iteration)
```bash
cd medrack
python3 -m venv .venv
./.venv/bin/pip install -e ./backend            # editable
MEDRACK_HOME=~/medrack-data ./.venv/bin/uvicorn medrack.dashboard.api.v1:app \
    --host 0.0.0.0 --port 8010 --reload
```

### Frontend (hot-reload dev server)
```bash
cd frontend
npm install
VITE_MEDRACK_API_BASE=http://localhost:8010/api/v1 npm run dev
```

Useful frontend scripts: `npm run dev`, `npm run build`, `npm run lint`,
`npm run format`.

### Windows note
The backend and frontend both develop fine on Windows (PowerShell). The
`install.sh`/`run.sh` scripts are bash and target Ubuntu; on Windows run the
uvicorn and npm commands directly as shown above.

See [DEPLOYMENT.md](DEPLOYMENT.md) for running it as a long-lived service and
[CONFIGURATION.md](CONFIGURATION.md) for all settings.
