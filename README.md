# MedRack

**A local-first RAG system that turns MBBS exam question banks into beautifully formatted, exam-ready answer PDFs.**

MedRack ingests medical textbooks (e.g. *Park's Preventive & Social Medicine*) into a vector knowledge base, extracts questions from exam-bank PDFs, retrieves the relevant textbook context for each question, and uses an LLM to write structured, exam-style answers — complete with section headings, bullet points, comparison **tables**, and **flowchart diagrams** — rendered into a polished, print-ready PDF.

It runs entirely on your own hardware. The LLM can be a free cloud model (Google Gemini) or a fully local model served with llama.cpp (e.g. Qwen/Qwopus 30B-A3B on a consumer GPU) — no data leaves your machines.

> **License:** Proprietary. All rights reserved. See [`LICENSE`](./LICENSE).

---

## What it does

```
Textbook PDF ──► ingest (OCR → chunk → embed) ──► ChromaDB vector index
                                                        │
Question-bank PDF ──► extract questions (10-/5-mark) ───┤
                                                        ▼
   For each question:  embed query → retrieve textbook chunks → rerank
                          → build prompt → LLM → structured answer
                                                        ▼
                     Render → beautiful multi-question PDF
                     (headings, bullets, tables, flowcharts)
```

### Highlights
- **Two-sided workflow** — a permanent textbook *knowledge base* + disposable *question banks*.
- **Mark-aware answers** — 10-mark questions get ~750-word answers, 5-mark get ~375-word, each with the right depth.
- **Rich formatting** — the model produces Markdown tables for comparisons and Graphviz flowcharts for processes (chain of infection, life cycles, etc.); both render natively in the PDF *and* the on-screen preview.
- **Preview-before-commit** — generate and review one answer, then approve to solve the whole bank into a single PDF.
- **Pluggable LLM** — Google Gemini (free tier), local llama.cpp, or Ollama, switchable with one env var.
- **Answer cache** — every generated answer is cached and re-usable; a dedicated tab lets you browse and manage them.
- **Runs on modest hardware** — designed and tested on an Ubuntu server driving a local Qwen 30B-A3B MoE model on an 8 GB RTX 3060 Ti over the LAN.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Vector store | ChromaDB |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384-dim) |
| PDF in | pypdf, pdfplumber, Tesseract OCR, poppler |
| PDF out | ReportLab (+ Graphviz for flowcharts) |
| LLM | Google Gemini / llama.cpp / Ollama (pluggable) |
| Frontend | React 19, TanStack Start + Router, Vite, Tailwind CSS v4, TypeScript |

---

## Repository layout

```
medrack/
├── backend/          # Python `medrack` package (pip-installable) + FastAPI API
│   ├── medrack/      # the package (ingest, retrieval, answer, dashboard, ...)
│   └── pyproject.toml
├── frontend/         # React / TanStack Start UI
│   └── src/
├── docs/             # Documentation (start here 👇)
├── install.sh        # One-shot Ubuntu installer
├── run.sh / stop.sh  # Start / stop the API + frontend
├── .env.example      # Runtime configuration template
└── README.md
```

---

## Quick start (Ubuntu)

Requires **Python 3.11+**, **Node 20+**, and internet access for the one-time dependency download.

```bash
git clone <your-repo-url> medrack
cd medrack

# 1. Install system deps, the backend (venv), and build the frontend
bash install.sh

# 2. Choose your LLM: edit .env
#    - Gemini:  uncomment the Gemini block, paste GEMINI_API_KEY
#    - Local:   set MEDRACK_LLM_BASE_URL to your llama.cpp server
nano .env

# 3. Start it
bash run.sh
```

Then open **http://localhost:3010** (UI). The API lives at **http://localhost:8010/api/v1** (docs at `/docs`). Stop everything with `bash stop.sh`.

Full instructions — including running a local model and accessing the UI from another device — are in [`docs/SETUP.md`](docs/SETUP.md).

---

## Using it (in the UI)

1. **Books** → upload a textbook PDF; wait for ingestion (OCR + embedding) to finish.
2. **Question Banks** → upload an exam-bank PDF; MedRack extracts the questions (segregating 10-mark and 5-mark).
3. **Workspace** → pick a bank + a book, set the answer lengths, **Generate Preview** for one question, review it, then **Approve** to solve the whole bank into one PDF.
4. **Cached Answers** → browse, view, and manage every generated answer.

See [`docs/USAGE.md`](docs/USAGE.md) for the detailed walkthrough.

---

## Documentation

| Doc | What's inside |
|-----|---------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the RAG pipeline works end-to-end; components and data flow |
| [`docs/SETUP.md`](docs/SETUP.md) | Installing on Ubuntu, dev setup on Windows, running a local llama.cpp model |
| [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) | Every environment variable and LLM-provider option |
| [`docs/USAGE.md`](docs/USAGE.md) | The full book → bank → solve → PDF workflow |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Running as a service, ports, updating, troubleshooting |

---

*MedRack is a personal project built for MBBS exam preparation. Verify frequently-revised Indian medical data against your current edition before an exam.*
