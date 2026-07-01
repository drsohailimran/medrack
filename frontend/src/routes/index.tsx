import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import {
  CheckCircle2,
  Download,
  FileText,
  Library,
  Loader2,
  Play,
  RotateCcw,
  Sparkles,
} from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { AnswerViewer } from "@/components/answer-viewer";
import { ProgressBar } from "@/components/progress-bar";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useJob } from "@/lib/use-job";
import type { GenerationResult, Marks, Subject } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Workspace — MedRack" },
      {
        name: "description",
        content: "Generate exam answers for a whole question module from your textbook.",
      },
    ],
  }),
  component: Workspace,
});

// Answer-length boxes persist so the user's preferred lengths stick.
function usePersistedNumber(key: string, fallback: number) {
  const [value, setValue] = useState<number>(() => {
    try {
      const v = localStorage.getItem(key);
      if (v != null && v !== "") return Number(v);
    } catch {
      /* ignore */
    }
    return fallback;
  });
  useEffect(() => {
    try {
      localStorage.setItem(key, String(value));
    } catch {
      /* ignore */
    }
  }, [key, value]);
  return [value, setValue] as const;
}

const SELECT_CLS =
  "mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary";

function Workspace() {
  const [bankName, setBankName] = useState("");
  const [bookId, setBookId] = useState("");
  const [words10, setWords10] = usePersistedNumber("medrack:words10", 750);
  const [words5, setWords5] = usePersistedNumber("medrack:words5", 375);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [downloadingSolved, setDownloadingSolved] = useState(false);
  const autoDownload = useRef(false);

  const { data: banks } = useQuery({
    queryKey: ["question-banks"],
    queryFn: () => api.listQuestionBanks(),
  });
  const { data: books } = useQuery({ queryKey: ["books"], queryFn: () => api.listBooks() });

  const { data: bankDetail } = useQuery({
    queryKey: ["bank-questions", bankName],
    queryFn: () => api.getBankQuestions(bankName),
    enabled: !!bankName,
  });
  const firstQuestion = bankDetail?.questions?.[0];
  // The preview uses the first question at its own marks (5 or 10, default 10).
  const previewMarks: Marks = firstQuestion?.marks === 5 ? 5 : 10;
  const previewWords = previewMarks === 5 ? words5 : words10;

  const indexedBooks = useMemo(() => (books ?? []).filter((b) => b.indexed), [books]);
  const selectedBook = useMemo(() => books?.find((b) => b.book_id === bookId), [books, bookId]);
  const subject: Subject =
    (selectedBook?.subject as Subject) || (bankDetail?.subject as Subject) || "psm";

  const preview = useMutation({
    mutationFn: () => {
      if (!bankName) throw new Error("Select a question module first.");
      if (!firstQuestion) throw new Error("This module has no questions to preview yet.");
      return api.generate({
        qid: firstQuestion.qid,
        question_text: firstQuestion.question_text,
        subject,
        marks: previewMarks,
        question_type: (firstQuestion.type as "theory" | "mcq") || "theory",
        book_id: bookId || undefined,
        word_count_target: previewWords,
      });
    },
    onSuccess: (data) => {
      setResult(data);
      setError(data.ok ? null : data.error || "Generation failed.");
    },
    onError: (e: Error) => setError(e.message),
  });

  // Reload-proof solve job (persists + resumes across a page refresh).
  const solve = useJob("medrack:solveJob");
  const solveMutation = useMutation({
    mutationFn: () => {
      if (!bankName) throw new Error("Select a question module first.");
      return api.solveBank({
        name: bankName,
        subject,
        book_id: bookId || undefined,
        marks: 10,
        words_5: words5,
        words_10: words10,
      });
    },
    onSuccess: (h) => {
      autoDownload.current = true; // this session started it → auto-download on finish
      solve.start(h.job_id);
    },
    onError: (e: Error) => setError(e.message),
  });

  const downloadSolvedPdf = async () => {
    if (!solve.job) return;
    setDownloadingSolved(true);
    setError(null);
    try {
      const r = (solve.job.result ?? {}) as { download_name?: string };
      const res = await fetch(api.jobPdfUrl(solve.job.job_id));
      if (!res.ok) throw new Error(`${res.status}`);
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u;
      a.download = r.download_name || `${bankName || "module"}-solved.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(u);
    } catch (e) {
      setError(`Solved PDF download failed: ${(e as Error).message}`);
    } finally {
      setDownloadingSolved(false);
    }
  };

  // Auto-download once when a solve finishes (only if started this session,
  // so a page reload that resumes a finished job doesn't re-download).
  useEffect(() => {
    if (solve.job?.status === "done" && autoDownload.current) {
      autoDownload.current = false;
      void downloadSolvedPdf();
    } else if (solve.job?.status === "error") {
      setError(solve.job.error ?? "Solving the module failed.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solve.job?.status]);

  const solving = solve.job != null && solve.job.status !== "done" && solve.job.status !== "error";
  const solveDone = solve.job?.status === "done";
  const solvedInfo = (solve.job?.result ?? {}) as { answered?: number; questions_total?: number };

  const downloadPreviewPdf = async () => {
    if (!result?.answer_text) return;
    setDownloadingPdf(true);
    setError(null);
    try {
      const blob = await api.renderAnswerPdf({
        qid: result.qid,
        subject,
        question_text: firstQuestion?.question_text || "",
        answer_text: result.answer_text,
        marks: previewMarks,
        question_type: (firstQuestion?.type as string) || "theory",
      });
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u;
      a.download = `medrack-${result.qid}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(u);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const wordCount = useMemo(
    () => result?.answer_text?.trim().split(/\s+/).filter(Boolean).length ?? 0,
    [result],
  );

  return (
    <AppShell>
      <div className="grid h-full min-h-0 grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)]">
        {/* LEFT: the workflow */}
        <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto border-r border-border bg-surface p-5">
          <div>
            <h1 className="font-display text-lg font-semibold">Generate Answers</h1>
            <p className="mt-1 text-xs text-muted-foreground">
              Pick a question module and a textbook, set the answer lengths, preview one answer —
              then approve to solve the whole module into a PDF.
            </p>
          </div>

          <Field
            label="1 · Question module"
            hint={bankDetail ? `${bankDetail.questions.length} questions` : undefined}
          >
            <select
              value={bankName}
              onChange={(e) => {
                setBankName(e.target.value);
                setResult(null);
                setError(null);
              }}
              className={SELECT_CLS}
            >
              <option value="">Select a question module…</option>
              {(banks ?? []).map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name} · {b.subject.toUpperCase()} · {b.question_count} Qs
                </option>
              ))}
            </select>
            {banks && banks.length === 0 && (
              <p className="mt-1 text-[11px] text-warning">
                No modules yet — upload one on the Question Banks page.
              </p>
            )}
          </Field>

          <Field label="2 · Textbook (knowledge base)">
            <select
              value={bookId}
              onChange={(e) => setBookId(e.target.value)}
              className={SELECT_CLS}
            >
              <option value="">Auto — all books in the module's subject</option>
              {indexedBooks.map((b) => (
                <option key={b.book_id} value={b.book_id}>
                  {b.title} · {b.subject.toUpperCase()} · {b.chunk_count} chunks
                </option>
              ))}
            </select>
            {books && indexedBooks.length === 0 && (
              <p className="mt-1 text-[11px] text-warning">
                No indexed books — upload a textbook on the Books page.
              </p>
            )}
          </Field>

          <Field label="3 · Answer length (words)">
            <div className="mt-1 grid grid-cols-2 gap-2">
              <LengthBox label="10-mark answers" value={words10} onChange={setWords10} />
              <LengthBox label="5-mark answers" value={words5} onChange={setWords5} />
            </div>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Each question is answered at the length for its own marks.
            </p>
          </Field>

          {firstQuestion && (
            <div className="rounded-md border border-border bg-background px-3 py-2 text-[11px] text-muted-foreground">
              <span className="font-medium text-foreground">
                Preview ({previewMarks}-mark → {previewWords} words):
              </span>{" "}
              {firstQuestion.question_text.slice(0, 120)}
              {firstQuestion.question_text.length > 120 ? "…" : ""}
            </div>
          )}

          <div className="mt-1 space-y-2">
            <Button
              className="w-full"
              onClick={() => {
                setError(null);
                preview.mutate();
              }}
              disabled={!bankName || !firstQuestion || preview.isPending || solving}
            >
              {preview.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Generating preview…
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" /> Generate Preview Answer
                </>
              )}
            </Button>
            <Button
              className="w-full bg-success text-success-foreground hover:bg-success/90"
              onClick={() => {
                setError(null);
                solveMutation.mutate();
              }}
              disabled={!result?.answer_text || solving || solveMutation.isPending}
              title="Generate answers for every question in the module and download one PDF"
            >
              {solving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Solving module…
                </>
              ) : (
                <>
                  <CheckCircle2 className="mr-2 h-4 w-4" /> Approve &amp; Solve Module
                </>
              )}
            </Button>
            {solving && solve.job && (
              <ProgressBar percent={solve.job.percent} label={solve.job.message || "Solving…"} />
            )}
            {solveDone && (
              <div className="rounded-md border border-success/30 bg-success/10 px-3 py-2 text-[12px] text-success">
                <div className="mb-1.5 font-medium">
                  Module solved — {solvedInfo.answered ?? "?"}/{solvedInfo.questions_total ?? "?"}{" "}
                  answered.
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full"
                  onClick={downloadSolvedPdf}
                  disabled={downloadingSolved}
                >
                  <Download className="mr-1.5 h-3.5 w-3.5" />
                  {downloadingSolved ? "Downloading…" : "Download Again"}
                </Button>
              </div>
            )}
            {error && (
              <p className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
                {error}
              </p>
            )}
          </div>
        </aside>

        {/* CENTER: preview */}
        <section className="flex min-h-0 flex-col">
          <div className="flex items-center justify-between gap-2 border-b border-border px-6 py-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/30">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="truncate font-display text-[15px] font-semibold">
                  {result ? "Preview answer" : "Answer preview"}
                </div>
                <div className="truncate text-[11px] text-muted-foreground">
                  {result
                    ? `${wordCount} words · ${result.token_count} tokens · ${result.latency_seconds.toFixed(1)}s`
                    : "Generate a preview to see a formatted answer"}
                </div>
              </div>
            </div>
            {result?.answer_text && (
              <Button
                variant="outline"
                size="sm"
                onClick={downloadPreviewPdf}
                disabled={downloadingPdf}
                title="Download this preview answer as a PDF"
              >
                <Download className="mr-1.5 h-3.5 w-3.5" /> {downloadingPdf ? "PDF…" : "PDF"}
              </Button>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-auto bg-background">
            {preview.isPending && (
              <div className="grid h-full place-items-center">
                <div className="text-center">
                  <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/30">
                    <Loader2 className="h-5 w-5 animate-spin" />
                  </div>
                  <div className="text-sm font-medium">Synthesizing answer</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Retrieving from the textbook → writing the answer
                  </div>
                </div>
              </div>
            )}
            {!preview.isPending && result?.answer_text && (
              <div>
                <div className="flex items-center gap-2 border-b border-border bg-success/10 px-6 py-2 text-[12px] text-success">
                  <Sparkles className="h-3.5 w-3.5" />
                  <span className="font-medium">Preview ready</span>
                  <span className="text-success/70">·</span>
                  <span>approve on the left to solve the whole module into a PDF</span>
                </div>
                {firstQuestion && (
                  <div className="mx-auto max-w-[80ch] px-8 pt-6">
                    <div className="rounded-md bg-primary px-4 py-3 text-sm font-semibold leading-snug text-primary-foreground">
                      Q. {firstQuestion.question_text}
                    </div>
                  </div>
                )}
                <AnswerViewer answer={result.answer_text} />
              </div>
            )}
            {!preview.isPending && result && !result.answer_text && (
              <CenterMessage
                title="No answer produced"
                body={result.error ?? "The backend returned an empty answer."}
              />
            )}
            {!preview.isPending && !result && <EmptyState hasSolve={!!solve.job} />}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function LengthBox({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="rounded-md border border-border bg-background px-3 py-2">
      <span className="block text-[11px] font-medium text-foreground">{label}</span>
      <div className="mt-1 flex items-baseline gap-1">
        <input
          type="number"
          min={50}
          max={3000}
          step={25}
          value={value}
          onChange={(e) => {
            const n = Number(e.target.value);
            if (!Number.isNaN(n)) onChange(Math.max(50, Math.min(3000, n)));
          }}
          className="w-full bg-transparent font-mono text-lg font-semibold tabular-nums outline-none"
        />
        <span className="text-[10px] text-muted-foreground">words</span>
      </div>
    </label>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </label>
        {hint ? <span className="text-[10px] text-muted-foreground">{hint}</span> : null}
      </div>
      {children}
    </div>
  );
}

function CenterMessage({ title, body }: { title: string; body: string }) {
  return (
    <div className="grid h-full place-items-center px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-warning/10 text-warning ring-1 ring-warning/30">
          <Sparkles className="h-5 w-5" />
        </div>
        <h2 className="font-display text-lg font-semibold">{title}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      </div>
    </div>
  );
}

function EmptyState({ hasSolve }: { hasSolve: boolean }) {
  return (
    <div className="grid h-full place-items-center px-6">
      <div className="max-w-md text-center">
        <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/30">
          {hasSolve ? <RotateCcw className="h-5 w-5" /> : <Library className="h-5 w-5" />}
        </div>
        <h2 className="font-display text-lg font-semibold">
          {hasSolve ? "Your last solve is on the left" : "Solve a question module"}
        </h2>
        <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
          Choose a question module and a textbook on the left, set the answer lengths, and click{" "}
          <span className="font-medium text-foreground">Generate Preview Answer</span>. Approve it
          to solve every question in the module and download one PDF.
        </p>
      </div>
    </div>
  );
}
