# Usage

The whole workflow happens in the web UI (`http://localhost:3010`). The nav has
six tabs: **Workspace, Books, Question Banks, Cached Answers, Logs, Settings**.

---

## 1. Add a textbook (Books)

The textbook is your permanent knowledge base — do this once per book.

1. Go to **Books → Upload**.
2. Select a subject (e.g. PSM) and upload the textbook PDF.
3. Ingestion runs in the background: read/OCR → chunk → embed → index. Progress
   is shown live. A large textbook (~1700 chunks) takes a few minutes.
4. When it shows as **indexed**, it's ready to use.

You can re-index or delete a book from the three-dots menu on each card.

---

## 2. Add a question bank (Question Banks)

1. Go to **Question Banks → Upload question bank**.
2. Choose the subject and upload the exam-bank PDF.
3. MedRack uses the LLM to extract the questions, automatically separating
   **10-mark** and **5-mark** questions.
4. Click a bank to **view** its extracted questions, or delete it.

> Tip: the extractor reads the whole document, so an 80-question bank is
> extracted in full — not just the first page.

---

## 3. Generate answers (Workspace)

This is the main screen.

1. **Select a question bank** and the **textbook** to ground answers in.
2. Set the **answer lengths** — separate boxes for 10-mark (default ~750 words)
   and 5-mark (default ~375 words).
3. Click **Generate Preview** to solve the *first* question. Review the answer
   in the preview pane — it shows the question banner, section headings,
   bullets, and any tables/flowcharts, formatted exactly like the PDF.
4. Happy with it? Click **Approve** to solve the **entire bank**. Progress is
   shown as `Answered N/total`; the job survives a page reload.
5. When done, **Download** the combined PDF (or **Download Again** later).

### Tables and flowcharts
The model adds these automatically where they fit:
- **Tables** for comparisons/classifications — questions like *"tabulate the
  differences between X and Y"* or *"compare …"*.
- **Flowcharts** for processes/cycles — *"chain of infection"*, *"natural
  history of disease"*, life cycles, referral pathways, etc.

They render in both the on-screen preview and the PDF. If a question doesn't
call for them, the answer is plain bullets — that's expected.

---

## 4. Manage cached answers (Cached Answers)

Every generated answer is cached (so re-solving is instant and free). The
**Cached Answers** tab groups answers by bank; you can:
- **view** any answer in the same formatted viewer,
- **delete** a single answer, or **delete all** for a bank.

> Cached answers keep the format they were generated with. After a prompt or
> renderer change (e.g. enabling tables/flowcharts), delete the old cached
> answers and re-solve to regenerate them with the new behaviour.

---

## 5. Settings & Logs

- **Settings** — backend/schema/pipeline versions, API base, and client-side
  preferences (default subject, marks, theme).
- **Logs** — searchable backend logs (ingestion, extraction, generation).

---

## Command line (optional)

The backend also exposes a `medrack` CLI (handy for scripting/headless use):

```bash
medrack init        # create data directories
medrack status      # dependencies + indexed counts
medrack version
```

The REST API is self-documenting at `http://localhost:8010/docs`.

---

## A note on accuracy

MedRack grounds answers in your textbook, but LLMs can still err on
frequently-revised specifics (latest NFHS figures, programme years, schedules).
**Verify current Indian data against your edition before an exam.**
