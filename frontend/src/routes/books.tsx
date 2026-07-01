import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { BookOpen, Plus, RefreshCw, Trash2, UploadCloud } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { ProgressBar } from "@/components/progress-bar";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api, KNOWN_SUBJECTS, type Subject } from "@/lib/api";
import { useJob } from "@/lib/use-job";
import { formatDate } from "@/lib/format";

export const Route = createFileRoute("/books")({
  head: () => ({
    meta: [
      { title: "Books — MedRack" },
      { name: "description", content: "Manage textbooks indexed into the MedRack library." },
    ],
  }),
  component: BooksPage,
});

function BooksPage() {
  const {
    data: books,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ["books"],
    queryFn: () => api.listBooks(),
  });

  const qc = useQueryClient();

  const [showImportDialog, setShowImportDialog] = useState(false);
  const [importSubject, setImportSubject] = useState<Subject>("psm");
  const [importTitle, setImportTitle] = useState("");
  const [importFile, setImportFile] = useState<File | null>(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const ingest = useJob("medrack:ingestJob");

  const importMutation = useMutation({
    mutationFn: () => {
      if (!importFile) throw new Error("Choose a PDF file to upload.");
      return api.uploadBook({
        file: importFile,
        subject: importSubject,
        title: importTitle.trim() || importFile.name.replace(/\.pdf$/i, ""),
        replace: replaceExisting,
      });
    },
    onSuccess: (handle) => {
      setImportError(null);
      ingest.start(handle.job_id);
    },
    onError: (err: Error) => setImportError(err.message),
  });

  // React to ingest job completion.
  useEffect(() => {
    const st = ingest.job?.status;
    if (st === "done") {
      const r = (ingest.job?.result ?? {}) as { chunks?: number; pages?: number };
      setActionMessage(
        `Ingested "${importTitle || importFile?.name || "book"}" — ${r.chunks ?? 0} chunks from ${r.pages ?? 0} pages indexed.`,
      );
      qc.invalidateQueries({ queryKey: ["books"] });
      setShowImportDialog(false);
      setImportFile(null);
      setImportTitle("");
      ingest.reset();
    } else if (st === "error") {
      setImportError(ingest.job?.error ?? "Ingestion failed.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ingest.job?.status]);

  const ingesting =
    ingest.job != null && ingest.job.status !== "done" && ingest.job.status !== "error";
  const busy = importMutation.isPending || ingesting;

  const deleteMutation = useMutation({
    mutationFn: (book_id: string) => api.removeBook(book_id),
    onSuccess: (data) => {
      if (data.ok === false) {
        setActionMessage(`Delete failed: ${data.error ?? "book not found"}`);
      } else {
        setActionMessage(
          `Deleted book — its indexed chunks were removed from the knowledge base. Upload a fresh copy anytime.`,
        );
      }
      qc.invalidateQueries({ queryKey: ["books"] });
    },
    onError: (err: Error) => setActionMessage(`Delete failed: ${err.message}`),
  });

  const subjectOptions = Array.from(
    new Set([
      ...KNOWN_SUBJECTS.map((s) => s.value),
      ...(books?.map((b) => b.subject).filter(Boolean) ?? []),
    ]),
  );

  return (
    <AppShell>
      <PageHeader
        eyebrow="Library"
        title="Books"
        description="Textbook PDFs indexed into the retrieval store. Every claim in a generated answer is grounded in chunks from these sources."
        actions={
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="mr-1.5 h-4 w-4" /> Refresh
            </Button>
            <Button onClick={() => setShowImportDialog(true)}>
              <Plus className="mr-1.5 h-4 w-4" /> Import book
            </Button>
          </div>
        }
      />
      {actionMessage && (
        <div className="mx-6 mt-4 flex items-center justify-between rounded-md border border-info/30 bg-info/10 px-3 py-2 text-[12px] text-info-foreground">
          <span>{actionMessage}</span>
          <button
            onClick={() => setActionMessage(null)}
            className="text-info-foreground/70 hover:text-info-foreground"
          >
            dismiss
          </button>
        </div>
      )}
      {showImportDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="surface-card w-full max-w-md p-6">
            <h2 className="text-lg font-semibold">Import Book</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Upload a PDF from this device. It is ingested into the knowledge base (extract → chunk
              → embed → index into ChromaDB) with live progress.
            </p>
            <div className="mt-4 space-y-3">
              <div>
                <label className="text-sm font-medium">PDF file</label>
                <label className="mt-1 flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border bg-background px-3 py-2 text-sm hover:border-primary/50">
                  <UploadCloud className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{importFile ? importFile.name : "Choose a PDF…"}</span>
                  <input
                    type="file"
                    accept="application/pdf"
                    className="hidden"
                    disabled={busy}
                    onChange={(e) => {
                      const f = e.target.files?.[0] ?? null;
                      setImportFile(f);
                      if (f && !importTitle) setImportTitle(f.name.replace(/\.pdf$/i, ""));
                    }}
                  />
                </label>
              </div>
              <div>
                <label className="text-sm font-medium">Subject</label>
                <select
                  value={importSubject}
                  onChange={(e) => setImportSubject(e.target.value as Subject)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                >
                  {subjectOptions.map((s) => (
                    <option key={s} value={s}>
                      {s.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">Book Title (optional)</label>
                <input
                  type="text"
                  placeholder="Auto-generated from filename if empty"
                  value={importTitle}
                  onChange={(e) => setImportTitle(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                />
              </div>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={replaceExisting}
                  onChange={(e) => setReplaceExisting(e.target.checked)}
                  disabled={busy}
                />
                Replace if this book is already in the knowledge base
              </label>
            </div>
            {ingesting && ingest.job && (
              <div className="mt-4">
                <ProgressBar
                  percent={ingest.job.percent}
                  label={ingest.job.message || "Ingesting…"}
                />
              </div>
            )}
            {importError && (
              <p className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
                {importError}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setShowImportDialog(false);
                  ingest.reset();
                  setImportError(null);
                }}
                disabled={importMutation.isPending}
              >
                {ingesting ? "Close" : "Cancel"}
              </Button>
              <Button onClick={() => importMutation.mutate()} disabled={busy || !importFile}>
                {busy ? "Ingesting…" : "Upload & ingest"}
              </Button>
            </div>
          </div>
        </div>
      )}
      <div className="p-6">
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-background/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Title</th>
                <th className="px-4 py-3 font-medium">Subject</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 text-right font-medium">Chunks</th>
                <th className="px-4 py-3 text-right font-medium">Indexed</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                [...Array(3)].map((_, i) => (
                  <tr key={i} className="border-t border-border">
                    <td colSpan={6} className="px-4 py-4">
                      <div className="h-5 w-full animate-pulse rounded bg-muted/40" />
                    </td>
                  </tr>
                ))}
              {books?.map((b) => (
                <tr
                  key={b.book_id}
                  className="border-t border-border transition-colors hover:bg-background/40"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20">
                        <BookOpen className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <div className="truncate font-medium text-foreground">{b.title}</div>
                        <div className="truncate font-mono text-[11px] text-muted-foreground">
                          {b.book_id}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge tone="primary">{b.subject.toUpperCase()}</StatusBadge>
                  </td>
                  <td className="px-4 py-3">
                    {b.indexed ? (
                      <StatusBadge tone="pass">indexed</StatusBadge>
                    ) : (
                      <StatusBadge tone="warn">indexing</StatusBadge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-muted-foreground">
                    {b.chunk_count.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground">
                    {formatDate(b.indexed_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      title="Delete book"
                      className="text-muted-foreground hover:text-destructive"
                      onClick={() => {
                        if (
                          confirm(
                            `Delete "${b.title}"? This removes its indexed chunks from the knowledge base. You can upload a fresh copy afterwards.`,
                          )
                        ) {
                          deleteMutation.mutate(b.book_id);
                        }
                      }}
                      disabled={deleteMutation.isPending && deleteMutation.variables === b.book_id}
                    >
                      <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Delete
                    </Button>
                  </td>
                </tr>
              ))}
              {books && books.length === 0 && (
                <tr className="border-t border-border">
                  <td colSpan={6} className="px-4 py-12 text-center text-sm text-muted-foreground">
                    No books yet. Click{" "}
                    <span className="font-medium text-foreground">Import book</span> to add your
                    first textbook.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
