# MedRack — Backend (`medrack` Python package)

FastAPI + RAG backend for MedRack. Ingests MBBS textbook PDFs into a ChromaDB
vector index, extracts questions from exam-bank PDFs, retrieves relevant
textbook context, and generates exam-style answers rendered to PDF.

This directory is a **pip-installable package**. It is normally installed and
run via the repo-root scripts — see the top-level `README.md` and
`docs/` for setup, configuration, and usage.

## Install (standalone)

```bash
python3 -m venv .venv
./.venv/bin/pip install .
```

## CLI

The install exposes a `medrack` command:

```bash
medrack init        # create the data directories under $MEDRACK_HOME
medrack status      # show dependencies + indexed counts
medrack version     # print version
```

## Run the API

```bash
uvicorn medrack.dashboard.api.v1:app --host 0.0.0.0 --port 8010
# interactive API docs at  http://localhost:8010/docs
```

## Package layout

| Path | Purpose |
|------|---------|
| `config.py` | Central configuration: paths, subjects, LLM providers, chunk/retrieval/answer settings |
| `cli.py` | Command-line entry point (`medrack init/status/version/...`) |
| `ingest/` | Textbook ingestion: PDF → OCR/text → chunk → embed → ChromaDB |
| `module/` | Question-bank PDF extraction (per-mark question segregation) |
| `retrieval/` | Adaptive retrieval: question analysis → chunk ranking → metadata-boost reranker |
| `answer/` | Prompt building, LLM client (multi-provider), answer generation, PDF rendering |
| `dashboard/` | FastAPI `/api/v1` REST API (backend for the frontend) + Gradio dashboard |
| `planner/`, `validation/` | Optional answer blueprinting and quality-gate stages |
| `utils/` | Logging and shared helpers |

See `docs/ARCHITECTURE.md` at the repo root for the full pipeline.
