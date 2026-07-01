import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ChevronDown, ChevronRight, Database, Eye, RefreshCw, Trash2, X } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { AnswerViewer } from "@/components/answer-viewer";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { formatTimestamp } from "@/lib/format";
import type { CacheEntry } from "@/lib/api";

export const Route = createFileRoute("/answers")({
  head: () => ({ meta: [{ title: "Cached Answers — MedRack" }] }),
  component: CachedAnswersPage,
});

const safeStem = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "");
const SINGLE_KEY = "__single__";

type Group = { key: string; label: string; module: string; isBank: boolean; entries: CacheEntry[] };

function CachedAnswersPage() {
  const qc = useQueryClient();
  const { data: entries } = useQuery({
    queryKey: ["cache-entries", "all"],
    queryFn: () => api.listCacheEntries({}),
  });
  const { data: banks } = useQuery({
    queryKey: ["question-banks"],
    queryFn: () => api.listQuestionBanks(),
  });
  const { data: status } = useQuery({
    queryKey: ["cache-status"],
    queryFn: () => api.getCacheStatus(),
  });

  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [viewQid, setViewQid] = useState<string | null>(null);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["cache-entries"] });
    qc.invalidateQueries({ queryKey: ["cache-status"] });
  };

  const deleteEntry = useMutation({
    mutationFn: ({ qid, module }: { qid: string; module?: string }) =>
      api.deleteCacheEntry(qid, module),
    onSuccess: refresh,
  });
  const deleteModule = useMutation({
    mutationFn: (module: string) => api.deleteCacheModule(module),
    onSuccess: refresh,
  });
  const deleteMany = useMutation({
    mutationFn: async (items: { qid: string; module?: string }[]) => {
      for (const it of items) await api.deleteCacheEntry(it.qid, it.module);
    },
    onSuccess: refresh,
  });

  // Group cached answers by their module; bank modules are labelled with the
  // bank name, everything else goes under "Single answers".
  const groups = useMemo<Group[]>(() => {
    const bankBySafe = new Map<string, string>();
    (banks ?? []).forEach((b) => bankBySafe.set(safeStem(b.name), b.name));
    const map = new Map<string, Group>();
    for (const e of entries ?? []) {
      const mod = e.module || "";
      const bankName = bankBySafe.get(mod);
      if (bankName) {
        if (!map.has(mod))
          map.set(mod, { key: mod, label: bankName, module: mod, isBank: true, entries: [] });
        map.get(mod)!.entries.push(e);
      } else {
        if (!map.has(SINGLE_KEY))
          map.set(SINGLE_KEY, {
            key: SINGLE_KEY,
            label: "Single answers (Workspace previews & tests)",
            module: "",
            isBank: false,
            entries: [],
          });
        map.get(SINGLE_KEY)!.entries.push(e);
      }
    }
    const arr = Array.from(map.values());
    // Banks first (alphabetical), single answers last.
    arr.sort((a, b) =>
      a.isBank === b.isBank ? a.label.localeCompare(b.label) : a.isBank ? -1 : 1,
    );
    return arr;
  }, [entries, banks]);

  const total = entries?.length ?? 0;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Cached Answers"
        description="Every answer MedRack has generated is cached here, grouped by question bank. Delete any you don't like — they'll be regenerated fresh next time you solve."
        actions={
          <Button variant="outline" onClick={refresh}>
            <RefreshCw className="mr-1.5 h-4 w-4" /> Refresh
          </Button>
        }
      />

      <div className="grid gap-3 px-6 py-4 sm:grid-cols-3">
        <StatCard label="Total cached answers" value={total} />
        <StatCard label="Question banks" value={groups.filter((g) => g.isBank).length} />
        <StatCard
          label="By subject"
          value={
            Object.entries(status?.by_subject ?? {})
              .map(([s, n]) => `${s.toUpperCase()}:${n}`)
              .join("  ") || "—"
          }
        />
      </div>

      <div className="space-y-4 px-6 pb-10">
        {groups.length === 0 && (
          <div className="surface-card p-10 text-center text-sm text-muted-foreground">
            No cached answers yet. Generate or solve some answers and they'll appear here.
          </div>
        )}

        {groups.map((g) => {
          const isCollapsed = collapsed[g.key];
          return (
            <div key={g.key} className="surface-card overflow-hidden">
              <div className="flex items-center justify-between gap-3 border-b border-border bg-surface-2 px-4 py-3">
                <button
                  className="flex min-w-0 items-center gap-2 text-left"
                  onClick={() => setCollapsed((c) => ({ ...c, [g.key]: !c[g.key] }))}
                >
                  {isCollapsed ? (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                  )}
                  <Database className="h-4 w-4 shrink-0 text-primary" />
                  <span className="truncate font-display text-sm font-semibold">{g.label}</span>
                  {g.isBank && <StatusBadge tone="primary">bank</StatusBadge>}
                  <span className="text-xs text-muted-foreground">
                    {g.entries.length} answer{g.entries.length === 1 ? "" : "s"}
                  </span>
                </button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  onClick={() => {
                    if (!confirm(`Delete all ${g.entries.length} cached answers in "${g.label}"?`))
                      return;
                    if (g.isBank) deleteModule.mutate(g.module);
                    else
                      deleteMany.mutate(g.entries.map((e) => ({ qid: e.qid, module: e.module })));
                  }}
                >
                  <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Delete all
                </Button>
              </div>

              {!isCollapsed && (
                <ul className="divide-y divide-border">
                  {g.entries.map((e) => (
                    <li key={e.qid} className="flex items-center gap-3 px-4 py-2.5">
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">
                          {e.question_text || <span className="font-mono text-xs">{e.qid}</span>}
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                          <span className="font-mono">{e.qid}</span>
                          <span>· {e.subject?.toUpperCase()}</span>
                          {e.target_word_count ? <span>· ~{e.target_word_count} w</span> : null}
                          {e.cached_at ? <span>· {formatTimestamp(e.cached_at)}</span> : null}
                          {e.is_stale ? <StatusBadge tone="warn">stale</StatusBadge> : null}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="View answer"
                        onClick={() => setViewQid(e.qid)}
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        title="Delete this cached answer"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => {
                          if (confirm(`Delete the cached answer for "${e.qid}"?`))
                            deleteEntry.mutate({ qid: e.qid, module: e.module });
                        }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {viewQid && <AnswerModal qid={viewQid} onClose={() => setViewQid(null)} />}
    </AppShell>
  );
}

function AnswerModal({ qid, onClose }: { qid: string; onClose: () => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["cache-entry", qid],
    queryFn: () => api.getCacheEntry(qid),
  });
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="surface-card flex max-h-[88vh] w-full max-w-3xl flex-col p-0"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-border px-6 py-3">
          <div className="min-w-0">
            <div className="truncate font-display text-sm font-semibold">{qid}</div>
            <div className="truncate text-xs text-muted-foreground">
              {data?.question_text || "Cached answer"}
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {isLoading && <p className="p-6 text-sm text-muted-foreground">Loading…</p>}
          {data?.answer_text ? (
            <AnswerViewer answer={data.answer_text} />
          ) : (
            !isLoading && <p className="p-6 text-sm text-muted-foreground">No answer text.</p>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="surface-card p-4">
      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}
