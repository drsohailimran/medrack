# Architecture

MedRack is a **retrieval-augmented answer generator**, not a classic
document-QA system. The corpus is one authoritative medical textbook that the
LLM already knows well; retrieval exists to *ground* answers in the textbook's
specific framing and data (Indian programmes, statistics, schedules), while the
model supplies the bulk of the medical knowledge.

This document explains how the whole thing fits together.

---

## 1. High-level flow

There are two ingestion paths and one generation path.

```
  ┌─────────────────────────── Knowledge base (permanent) ──────────────────────────┐
  │ Textbook PDF ─► read/OCR ─► chunk (1000 tok / 200 overlap) ─► embed ─► ChromaDB  │
  └─────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────── Question banks (disposable) ─────────────────────────┐
  │ Exam-bank PDF ─► LLM extraction ─► questions tagged 10-mark / 5-mark ─► stored   │
  └─────────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────── Answer generation ───────────────────────────────┐
  │ question ─► embed ─► retrieve top-k ─► rerank ─► top-N chunks                     │
  │          ─► build prompt (subject-aware) ─► LLM ─► answer text                    │
  │          ─► clean + parse ─► render (bullets / headings / tables / flowcharts)    │
  │          ─► cache + PDF                                                           │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Components (`backend/medrack/`)

### `config.py` — single source of truth
Every tunable lives here: data paths, the list of supported subjects and their
per-subject prompt context (reference textbook, Indian-context string, key
sources), the **LLM provider registry**, chunk/retrieval settings, word-count
targets, and cache-version numbers. Most values can be overridden by
environment variables (see [CONFIGURATION.md](CONFIGURATION.md)).

### `ingest/` — building the knowledge base
1. **read** the PDF (pypdf / pdfplumber); fall back to **Tesseract OCR** for
   scanned pages (≥ 500 chars/page threshold, DPI 300).
2. **chunk** the text with a sliding window: `CHUNK_SIZE_TOKENS = 1000`,
   `CHUNK_OVERLAP_TOKENS = 200` (`ingest/chunk.py`).
3. **embed** each chunk with `sentence-transformers/all-MiniLM-L6-v2` (384-dim).
4. **index** into ChromaDB, one collection per subject (`kb_<subject>`), with a
   `manifest.json` tracking indexed books.

### `module/` — extracting questions from an exam bank
`module/llm_extract.py` sends the bank PDF's text (in page batches) to the LLM
and asks it to return a clean list of questions. It detects **mark sections** —
banks usually group "10-mark questions" and "5-mark questions" under headings —
and tags each extracted question with its marks so answers get the right length.
Questions are de-duplicated on full normalized text.

### `retrieval/` — getting the right context
`retrieve_for_question()` composes:
- **question analysis** (`analyzer.py`) — infers target sections/intent,
- **strategy** — a `top_k` (default 8) plus a mandatory subject filter,
- a **metadata-boost reranker** (`reranker.py`) — deterministic; it *reorders*
  the vector hits using metadata signals but never replaces vector similarity.

The prompt then receives the top **5** chunks, each truncated to 1500 chars, to
keep the LLM input at a few thousand tokens.

> A semantic cross-encoder reranker (BGE) and stronger embeddings are supported
> as a future upgrade — the reranker base class is built for it — but are
> intentionally *not* enabled, because for this use case the model's own
> knowledge, lightly grounded, already produces high-quality answers.

### `answer/` — the heart of the system
- **`prompt.py`** — builds the theory/MCQ prompts. Subject-aware (injects the
  reference textbook, Indian-context string, and analytical framework). Encodes
  the formatting rules: point form, section headings, **tables** for
  comparisons, and **one Graphviz flowchart** for processes when useful. The
  word-count target is for the *written explanation only* — tables/flowcharts
  are additional and must not shorten the answer.
- **`llm.py`** — the provider-agnostic LLM client. One method per wire format:
  `_try_gemini` (Google `generateContent`), `_try_ollama` (`/api/generate`),
  `_try_openai` (llama.cpp / OpenAI `/v1/chat/completions`). Handles rate-limit
  retries (per-minute waits vs. daily caps), and disables model "thinking" where
  supported to keep answers on-length.
- **`generate.py`** — orchestrates one answer: embed → retrieve → build prompt →
  call the LLM with a token budget (`target × 1.4 + 500`, the `+500` reserving
  room for table/flowchart markup) → clean → cache.
- **`render.py` / `render_full.py`** — parse the answer text into blocks
  (headings, bullets, tables, diagrams) and render them:
  - `render_preview_pdf` — a single answer (used by "Generate Preview").
  - `render_full_module_pdf` — the whole bank as one styled PDF (navy cover,
    Contents, per-question navy banners, running header/footer, continuous flow).
  - Tables become styled ReportLab tables; DOT blocks are rendered to PNG via
    the `dot` CLI and embedded as images.

### `dashboard/` — the API
`dashboard/api/v1.py` is the FastAPI app (`medrack.dashboard.api.v1:app`) that
the frontend talks to. It exposes library management (books, banks), async jobs
(ingest, extract, solve-bank), single-answer generation, PDF rendering
(including `POST /render/graphviz` for the preview), the answer cache, logs, and
version info. Long tasks run on background threads and report progress via a job
registry (`GET /jobs/{id}`). A Gradio operator dashboard also lives here.

### `cli.py`, `planner/`, `validation/`, `utils/`
- `cli.py` — `medrack init/status/version` and ingestion commands.
- `planner/`, `validation/` — optional answer-blueprint and quality-gate stages
  (present, not on the default hot path).
- `utils/` — logging and helpers.

---

## 3. Answer text format (the block model)

The LLM returns Markdown-ish text. Both the PDF renderer (`render.py`) and the
web viewer (`frontend/src/components/answer-viewer.tsx`) parse it into the same
block types, so the preview matches the PDF:

| Block | How the model writes it | Rendered as |
|-------|-------------------------|-------------|
| Heading | a short standalone line, or `**Bold line**` | navy section heading |
| Main bullet | `• text` or `* text` | bullet |
| Sub-bullet | `– text` / `- text` | indented bullet |
| Bold | `**term**` | **bold** |
| Table | Markdown table (`\| … \|` + `\|---\|`) | bordered table, navy header |
| Flowchart | fenced ` ```dot … ``` ` (Graphviz) | rendered diagram image |

Because the model alternates between `•`/plain-heading style and Markdown
`*`/`**bold**` style, the parser accepts **both**.

---

## 4. The LLM provider abstraction

`config.LLM_PROVIDERS` is a registry keyed by provider name. Each entry declares
the base URL, model, wire format (`gemini` / `ollama` / `openai`), auth header,
API-key env var, and timeout. `MEDRACK_LLM_PROVIDER` selects the active one;
`MEDRACK_LLM_BASE_URL` / `MEDRACK_LLM_MODEL` / `MEDRACK_LLM_TIMEOUT` override it.
Adding a new provider is usually just a new dict entry (see
[CONFIGURATION.md](CONFIGURATION.md)).

Supported out of the box: **gemini** (cloud, free tier), **llamacpp** (local
OpenAI-compatible server — the recommended local option, supports MoE offload),
**ollama** (local), plus generic **claude**/**opencode** entries.

---

## 5. Data on disk (`MEDRACK_HOME`)

```
$MEDRACK_HOME/
├── books/<subject>/          # uploaded textbook PDFs
├── index/                    # ChromaDB collections + manifest.json
├── modules/<subject>/<name>/ # extracted question banks
├── answers/<module>/         # cached answers (JSON, per question)
├── output/                   # generated PDFs
└── logs/
```

The cache key for an answer includes the prompt/retrieval/renderer versions and
the embedding-model name, so changing any of them safely invalidates stale
answers.

---

## 6. Frontend (`frontend/src/`)

React 19 + TanStack Start (SSR via Nitro) + Tailwind v4. File-based routing:

| Route | Page |
|-------|------|
| `index.tsx` | **Workspace** — bank + book selection, length controls, preview, approve → solve |
| `books.tsx` | **Books** — upload/manage textbooks, ingestion progress |
| `question-banks.tsx` | **Question Banks** — upload banks, view/delete extracted questions |
| `answers.tsx` | **Cached Answers** — browse/view/delete cached answers by bank |
| `logs.tsx` | **Logs** — backend log viewer |
| `settings.tsx` | **Settings** — versions and client preferences |

`src/lib/api/client.ts` is the typed API client; it reads
`VITE_MEDRACK_API_BASE` (baked at build time). `use-job.ts` persists running
jobs to `localStorage` so progress survives a page reload. `answer-viewer.tsx`
renders the block model above (and fetches flowchart images from the backend's
`/render/graphviz` endpoint).

---

## 7. Why these choices

- **Single LLM call per question**, not a multi-agent chain — simpler, cheaper,
  and the answers are already exam-grade.
- **One textbook, model-heavy answering** — retrieval is a grounding nudge, so a
  small embedding model + metadata reranker is enough (see the note in §2).
- **Local-first** — Gemini for convenience, llama.cpp for full privacy and zero
  marginal cost; the same pipeline drives both.
