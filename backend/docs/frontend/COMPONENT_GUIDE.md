# Component Guide

This document describes every frontend screen and the
components it contains.

The production frontend is built with **Lovable**. Lovable
should generate the components; this document is the
specification.

---

## Top-level layout

```
+--------------------------------------------------+
| Top bar: MedRack | Version | Settings | Help    |
+------+-------------------------------------------+
|      |                                           |
| Side |                                           |
| nav  |             Main content                 |
|      |                                           |
|      |                                           |
+------+-------------------------------------------+
```

**Top bar**: MedRack logo, current version (from
`/api/v1/version`), Settings link, Help link.

**Side nav**: Library, Generate, Cache, Benchmarks, Logs,
Settings.

**Main content**: the current page.

---

## Screen 1: Dashboard (home)

**Purpose**: Welcome screen. Shows current state of the
system.

**Required data**:
- `GET /api/v1/library/books` (count)
- `GET /api/v1/cache/status` (total, stale)
- `GET /api/v1/version`

**Components**:
- 3 stat cards: "Books: N", "Cached answers: N (M stale)",
  "Version: 0.3.0"
- A "Quick start" panel with 3 actions: "Import book",
  "Generate answer", "Browse cache"
- A "Recent activity" panel (last 10 generation log entries)

**Empty state**: Show a welcome message with a video
tutorial link and the 3 quick-start actions.

**Error state**: Show a banner with the API error and a
"Retry" button.

---

## Screen 2: Library

**Purpose**: Manage textbooks.

**Required data**:
- `GET /api/v1/library/books`

**Components**:
- Header: "Library" title, "Import book" button
- Table: columns = book_id, title, subject, indexed,
  chunks, actions
- Each row: status badge (indexed/indexing/failed), action
  menu (reindex, remove, view)

**Sub-screens / modals**:
- **Import Book modal**: file picker, subject dropdown,
  title field, "Import" button
- **Remove Book confirmation**: "Are you sure? The PDF will
  be moved to trash."
- **Ingestion progress modal**: shows the live status from
  `GET /api/v1/library/ingestion-status/{book_id}`

**Empty state**: "No books yet. Click 'Import book' to add
your first textbook."

---

## Screen 3: Question Banks

**Purpose**: List available question banks.

**Required data**:
- `GET /api/v1/library/question-banks`

**Components**:
- Header: "Question Banks" title
- Table: columns = name, version, subject, question_count
- No upload (banks are operator-managed)

**Empty state**: "No question banks available."

---

## Screen 4: Generate (workspace)

**Purpose**: Generate an answer to a question.

**Required data**:
- None initially

**Components**:
- Left panel: question form
  - Question text (textarea, multi-line)
  - Subject (psm/fmt)
  - Marks (5/10)
  - Question type (theory/mcq)
  - Optional: book_id, chapter
  - "Generate" button
- Right panel: answer view
  - When no answer: "Generate an answer to see it here."
  - When generating: spinner with "Generating answer..."
  - When done: sectioned view of the answer, validation
    report, "Download PDF" link, "Revise" button, "View in
    cache" link

**Loading state**: full-page spinner overlay with "This may
take up to 30 seconds."

**Error state**: red banner with the error message and a
"Retry" button.

**Success state**:
- Answer text rendered with section headings
- Validation report panel: "Passed: 7/9 rules" with a
  collapsible list
- "Download PDF" button (opens the PDF in a new tab)
- "Revise" button (opens a modal to edit the question)
- "View in cache" link (navigates to the cache page)

---

## Screen 5: Cache

**Purpose**: Browse and manage cached answers.

**Required data**:
- `GET /api/v1/cache/entries`
- `GET /api/v1/cache/status`

**Components**:
- Header: "Cache" title, status badges (total, stale by
  subject)
- Filters: subject dropdown, "stale only" toggle, search
  box
- Table: columns = qid, subject, target_word_count, is_stale,
  validation_score, actions
- Each row: click to expand, "Re-answer" button (if stale)

**Sub-screens / modals**:
- **Cache entry detail panel**: shows the full answer,
  question text, validation report, version info
- **Re-answer confirmation**: "This will mark the entry as
  stale and re-generate. Continue?"
- **Bulk re-answer modal**: shows the stale qids from
  `GET /api/v1/questions/stale?dry_run=true` with a
  confirmation step

**Empty state**: "No cached answers yet. Generate an answer
to see it here."

---

## Screen 6: Benchmarks

**Purpose**: View benchmark history and compare runs.

**Required data**:
- `GET /api/v1/benchmarks/runs`

**Components**:
- Header: "Benchmarks" title
- Table: columns = run_id, timestamp, llm_mode, n_questions,
  n_success, cache_hit_rate, total_tokens, avg_latency,
  actions
- Each row: click to expand and show the full report
- "Compare 2 runs" button (select 2 rows)

**Sub-screens / modals**:
- **Compare modal**: shows a side-by-side table of run_a vs
  run_b with the deltas
- **Run detail view**: shows the full JSON report in a
  tree view

**Empty state**: "No benchmarks yet. Benchmarks are run by
the operator."

---

## Screen 7: Pipeline Inspector

**Purpose**: Inspect each pipeline stage for a question.

**Required data**:
- `GET /api/v1/pipeline/inspect` (on submit)

**Components**:
- Top: question form (question text, subject, marks)
- "Inspect" button
- Below: 6 tabs (Planner, Blueprint, Retrieval, Reranker,
  Writer, Validator)
- Each tab: shows the stage's `output` as a JSON tree
- Latency badge in each tab

**Empty state**: "Enter a question and click 'Inspect' to
see the pipeline stages."

---

## Screen 8: Logs

**Purpose**: View backend logs.

**Required data**:
- `GET /api/v1/logs/{name}` (on tab switch)
- `GET /api/v1/logs/{name}/search` (on search)

**Components**:
- Header: "Logs" title
- 4 tabs: Ingestion, Generation, Validation, Benchmark
- Each tab: scrollable list of log entries (most recent
  first)
- Search box: searches the active log

**Empty state**: "No log entries yet."

---

## Screen 9: Settings

**Purpose**: Display backend configuration.

**Required data**:
- `GET /api/v1/version`

**Components**:
- "Backend version" section
- "Pipeline versions" table
- "Benchmark baseline" link
- (Future) "Frontend settings" section (theme, default
  subject, etc.) — purely client-side, no API

**Empty state**: n/a (always has data)

---

## Reusable components

These should be implemented once and reused:

- `StatCard` — large number + label
- `StatusBadge` — colored badge (indexed/indexing/failed,
  pass/warn/fail, stale/fresh)
- `SectionViewer` — renders a MedRack answer with section
  headings
- `JsonTree` — renders JSON with collapsible nodes
- `Toast` / `Notification` — transient messages
- `LoadingSpinner` — full-page or inline
- `ErrorBanner` — red banner with retry
- `EmptyState` — illustration + message + CTA
- `ConfirmDialog` — modal for destructive actions
- `FileUpload` — drag-and-drop file picker
- `ProgressBar` — long-running progress (e.g. ingestion)
- `PdfViewer` — embedded PDF preview

## Accessibility

All components should:
- Use semantic HTML (button, nav, main, etc.)
- Support keyboard navigation
- Have proper aria-labels
- Have sufficient color contrast (WCAG AA minimum)
- Support screen readers
