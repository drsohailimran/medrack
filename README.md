# MedRack

Local RAG system for MBBS theory-exam answer generation. Ingests MBBS textbooks as a permanent knowledge base, extracts questions from exam module PDFs, and produces exam-style answers as PDFs.

## Status

**Stage 2.1 — Init** (foundation only). Working: directory structure, manifest schema, config, CLI (init/status/version). Coming next: KB ingest, module ingest, preview, full batch, dashboard, Telegram.

## Quick start

```bash
# Initialize data directories
medrack init

# Check status (deps + indexed counts)
medrack status
```

## Architecture

Single-pipeline RAG (one LLM call per question, not multi-agent). Three interfaces: Telegram bot (daily use), Gradio dashboard at `localhost:7860` (KB management), CLI (foundation). Preview-before-finalize flow: one answer first, user approves, then full batch.

## Layout

```
~/.hermes/medrack/
├── books/<subject>/        # KB PDFs (permanent)
├── modules/<subject>/<name>/  # Question-bank PDFs
├── index/                  # ChromaDB vectors + manifest.json
├── answers/                # Cached answers (re-runnable)
├── output/                 # Final PDFs
├── logs/                   # Operation logs
└── medrack/                # This package
    ├── cli.py
    ├── config.py
    ├── ingest/  module/  answer/  render/  bot/  dashboard/  utils/
    └── tests/
```

## Subjects (locked)

psm, fmt, medicine, surgery, ortho, obgyn, anesthesia, pediatrics, ent, ophthalmology.

## Documentation

- Plan: `~/.hermes/plans/20260626_154024/plan.md`
- Skills: `medrack` (use), `medrack-build` (develop), `pdf-rag-qa-system` (parent)
