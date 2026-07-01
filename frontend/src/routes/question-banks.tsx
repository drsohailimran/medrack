import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Eye, FileUp, Library, Trash2, Upload, X } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { ProgressBar } from "@/components/progress-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useJob } from "@/lib/use-job";
import { formatTimestamp } from "@/lib/format";

export const Route = createFileRoute("/question-banks")({
  head: () => ({ meta: [{ title: "Question Banks — MedRack" }] }),
  component: QuestionBanksPage,
});

const KNOWN_SUBJECTS = [
  "psm",
  "fmt",
  "medicine",
  "surgery",
  "obgyn",
  "pediatrics",
  "ortho",
  "ent",
  "ophthalmology",
  "anesthesia",
];

function QuestionBanksPage() {
  const { data } = useQuery({
    queryKey: ["question-banks"],
    queryFn: () => api.listQuestionBanks(),
  });

  const [showUpload, setShowUpload] = useState(false);
  const [bankName, setBankName] = useState("regression-v1");
  const [bankSubject, setBankSubject] = useState("psm");
  const [bankVersion, setBankVersion] = useState("v1");
  const [pickedFile, setPickedFile] = useState<File | null>(null);
  const [result, setResult] = useState<{
    ok: boolean;
    question_count?: number;
    error?: string;
  } | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);
  const qc = useQueryClient();

  // View-questions modal.
  const [viewBank, setViewBank] = useState<string | null>(null);
  const { data: bankDetail, isLoading: loadingDetail } = useQuery({
    queryKey: ["bank-questions", viewBank],
    queryFn: () => api.getBankQuestions(viewBank as string),
    enabled: !!viewBank,
  });

  const deleteBank = useMutation({
    mutationFn: (name: string) => api.deleteBank(name),
    onSuccess: (r) => {
      setResult(
        r.ok ? { ok: true, question_count: 0 } : { ok: false, error: r.error ?? "delete failed" },
      );
      qc.invalidateQueries({ queryKey: ["question-banks"] });
    },
    onError: (e: Error) => setResult({ ok: false, error: e.message }),
  });

  const extract = useJob("medrack:extractJob");

  const upload = useMutation({
    mutationFn: async (file: File) =>
      api.uploadQuestionBank({ file, name: bankName, subject: bankSubject, version: bankVersion }),
    onSuccess: (handle) => {
      setResult(null);
      extract.start(handle.job_id);
    },
    onError: (err: Error) => {
      setResult({ ok: false, error: err.message });
    },
  });

  // React to extraction job completion.
  useEffect(() => {
    const st = extract.job?.status;
    if (st === "done") {
      const r = (extract.job?.result ?? {}) as {
        bank?: { question_count?: number };
        warning?: string;
      };
      setResult({
        ok: true,
        question_count: r.bank?.question_count ?? 0,
        error: r.warning ?? undefined,
      });
      qc.invalidateQueries({ queryKey: ["question-banks"] });
      setShowUpload(false);
      setPickedFile(null);
      if (fileRef.current) fileRef.current.value = "";
      extract.reset();
    } else if (st === "error") {
      setResult({ ok: false, error: extract.job?.error ?? "Extraction failed." });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extract.job?.status]);

  const extracting =
    extract.job != null && extract.job.status !== "done" && extract.job.status !== "error";
  const busy = upload.isPending || extracting;

  const banks = data ?? [];

  return (
    <AppShell>
      <PageHeader
        eyebrow="Library"
        title="Question Banks"
        description="Upload a question-bank PDF and the backend extracts the questions and saves them as a regression dataset. The bank then appears in the Workspace's bank selector."
        actions={
          <Button onClick={() => setShowUpload(true)}>
            <Upload className="mr-1.5 h-4 w-4" /> Upload question bank
          </Button>
        }
      />

      {result && (
        <div
          className={
            "mx-6 mt-4 flex items-center justify-between rounded-md border px-3 py-2 text-[12px] " +
            (result.ok
              ? "border-success/30 bg-success/10 text-success"
              : "border-destructive/30 bg-destructive/10 text-destructive")
          }
        >
          <span>
            {result.ok
              ? `Uploaded bank "${bankName}" · ${result.question_count} questions extracted.`
              : `Upload failed: ${result.error ?? "unknown error"}`}
          </span>
          <button onClick={() => setResult(null)} className="text-current/70 hover:text-current">
            dismiss
          </button>
        </div>
      )}

      <div className="grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
        {banks.map((b) => (
          <div
            key={b.name}
            role="button"
            tabIndex={0}
            onClick={() => setViewBank(b.name)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") setViewBank(b.name);
            }}
            className="surface-card group relative flex cursor-pointer flex-col gap-3 p-5 transition-colors hover:bg-surface-2 hover:ring-1 hover:ring-primary/30"
            title="Click to view the questions in this bank"
          >
            <div className="flex items-start justify-between">
              <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20">
                <Library className="h-5 w-5" />
              </div>
              <div className="flex items-center gap-1.5">
                <StatusBadge tone="primary">{b.subject.toUpperCase()}</StatusBadge>
                <button
                  title="Delete this question bank"
                  className="rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete question bank "${b.name}"? This cannot be undone.`)) {
                      deleteBank.mutate(b.name);
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
            <div>
              <div className="font-display text-base font-semibold tracking-tight">{b.name}</div>
              <div className="font-mono text-[11px] text-muted-foreground">{b.version}</div>
            </div>
            <div className="mt-auto flex items-baseline gap-2">
              <span className="font-mono text-2xl font-semibold tabular-nums">
                {b.question_count}
              </span>
              <span className="text-xs text-muted-foreground">questions</span>
            </div>
            <div className="flex items-center gap-1 text-[11px] text-primary/80">
              <Eye className="h-3 w-3" /> View questions
            </div>
          </div>
        ))}

        {banks.length === 0 && (
          <div className="surface-card col-span-full flex flex-col items-center justify-center gap-3 p-10 text-center">
            <div className="grid h-12 w-12 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20">
              <Library className="h-6 w-6" />
            </div>
            <div>
              <div className="font-display text-base font-semibold">No question banks yet</div>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Upload a question-bank PDF. The backend extracts the questions using the same
                module-extraction pipeline it uses for module ingestion and persists the bank as
                JSON.
              </p>
            </div>
            <Button onClick={() => setShowUpload(true)}>
              <FileUp className="mr-1.5 h-4 w-4" /> Upload question bank
            </Button>
          </div>
        )}
      </div>

      {viewBank && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setViewBank(null)}
        >
          <div
            className="surface-card flex max-h-[85vh] w-full max-w-2xl flex-col p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-lg font-semibold">{viewBank}</h2>
                <p className="text-xs text-muted-foreground">
                  {bankDetail
                    ? `${bankDetail.questions.length} questions · ${(bankDetail.subject || "").toUpperCase()}`
                    : "Loading…"}
                </p>
              </div>
              <button
                onClick={() => setViewBank(null)}
                className="rounded p-1 text-muted-foreground hover:bg-background hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="mt-4 min-h-0 flex-1 overflow-y-auto">
              {loadingDetail && <p className="text-sm text-muted-foreground">Loading questions…</p>}
              {bankDetail && bankDetail.questions.length === 0 && (
                <p className="rounded-md border border-border bg-surface px-3 py-4 text-sm text-muted-foreground">
                  This bank has no extracted questions. Theory-question extraction needs the LLM —
                  re-upload if it was extracted before the LLM was configured.
                </p>
              )}
              {bankDetail && bankDetail.questions.length > 0 && (
                <ol className="space-y-2">
                  {bankDetail.questions.map((q, i) => (
                    <li
                      key={q.qid || i}
                      className="rounded-md border border-border bg-surface px-3 py-2 text-sm"
                    >
                      <div className="flex items-start gap-2">
                        <span className="mt-0.5 font-mono text-[11px] text-muted-foreground">
                          {i + 1}.
                        </span>
                        <div className="min-w-0">
                          <p className="text-foreground">{q.question_text}</p>
                          <div className="mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                            {q.marks ? <span>{q.marks} marks</span> : null}
                            {q.section ? <span>· {q.section}</span> : null}
                            {q.type ? <span>· {q.type}</span> : null}
                          </div>
                        </div>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </div>
            <div className="mt-4 flex justify-end">
              <Button variant="outline" onClick={() => setViewBank(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="surface-card w-full max-w-lg p-6">
            <h2 className="text-lg font-semibold">Upload question bank</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Select a PDF containing a list of questions (MCQ or theory). The backend runs the
              module-extraction pipeline and saves the result as a bank.
            </p>

            <div className="mt-4 space-y-3">
              <Field label="Bank name">
                <input
                  value={bankName}
                  onChange={(e) => setBankName(e.target.value)}
                  placeholder="e.g. psm-3rd-year-mock"
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Subject">
                  <select
                    value={bankSubject}
                    onChange={(e) => setBankSubject(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  >
                    {KNOWN_SUBJECTS.map((s) => (
                      <option key={s} value={s}>
                        {s.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Version">
                  <input
                    value={bankVersion}
                    onChange={(e) => setBankVersion(e.target.value)}
                    className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  />
                </Field>
              </div>
              <Field label="PDF file">
                <input
                  ref={fileRef}
                  type="file"
                  accept="application/pdf"
                  onChange={(e) => setPickedFile(e.target.files?.[0] ?? null)}
                  className="block w-full cursor-pointer rounded-md border border-dashed border-border bg-background px-3 py-3 text-sm file:mr-3 file:rounded file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary-foreground hover:border-primary/50"
                />
                {pickedFile && (
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    Selected: <span className="font-mono">{pickedFile.name}</span> (
                    {Math.round(pickedFile.size / 1024)} KB)
                  </p>
                )}
              </Field>
            </div>

            {extracting && extract.job && (
              <div className="mt-4">
                <ProgressBar
                  percent={extract.job.percent}
                  label={extract.job.message || "Extracting questions…"}
                />
              </div>
            )}
            {upload.isError && (
              <p className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
                {upload.error.message}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowUpload(false);
                  setPickedFile(null);
                  extract.reset();
                  if (fileRef.current) fileRef.current.value = "";
                }}
                disabled={upload.isPending}
              >
                {extracting ? "Close" : "Cancel"}
              </Button>
              <Button
                onClick={() => pickedFile && upload.mutate(pickedFile)}
                disabled={!pickedFile || !bankName.trim() || busy}
              >
                {busy ? (
                  <>
                    <Upload className="mr-1.5 h-4 w-4 animate-pulse" /> Extracting…
                  </>
                ) : (
                  <>
                    <Upload className="mr-1.5 h-4 w-4" /> Upload &amp; extract
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {banks.length > 0 && (
        <div className="px-6 pb-6 text-[10px] text-muted-foreground">
          Last refreshed at {formatTimestamp(new Date().toISOString())}
        </div>
      )}
    </AppShell>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}
