import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Download, Filter, RefreshCw, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatTimestamp } from "@/lib/format";

export const Route = createFileRoute("/history")({
  head: () => ({ meta: [{ title: "History — MedRack" }] }),
  component: HistoryPage,
});

function HistoryPage() {
  const [subject, setSubject] = useState<string>("all");
  const [staleOnly, setStaleOnly] = useState(false);
  const [query, setQuery] = useState("");

  const qc = useQueryClient();

  const { data: status } = useQuery({
    queryKey: ["cache-status"],
    queryFn: () => api.getCacheStatus(),
  });
  const { data: entries, isLoading } = useQuery({
    queryKey: ["cache-entries", subject, staleOnly],
    queryFn: () =>
      api.listCacheEntries({
        subject: subject === "all" ? undefined : subject,
        stale_only: staleOnly,
      }),
  });

  // Derive subject filter list from the actual cache entries so the user
  // can filter to any subject that has cached answers, not just the
  // hard-coded PSM/FMT.
  const subjectOptions = useMemo(() => {
    const set = new Set<string>(["all"]);
    entries?.forEach((e) => set.add(e.subject));
    return Array.from(set);
  }, [entries]);

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["cache-entries"] });
    qc.invalidateQueries({ queryKey: ["cache-status"] });
  };

  const exportJson = () => {
    if (!entries || entries.length === 0) return;
    const blob = new Blob([JSON.stringify(entries, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `medrack-cache-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const filtered = entries?.filter((e) => e.qid.toLowerCase().includes(query.toLowerCase()));

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="History"
        description="Every cached answer with its validation score, staleness, and pipeline versions."
        actions={
          <>
            <Button variant="outline" onClick={refresh}>
              <RefreshCw className="mr-1.5 h-4 w-4" /> Refresh
            </Button>
            <Button onClick={exportJson} disabled={!entries || entries.length === 0}>
              <Download className="mr-1.5 h-4 w-4" /> Export
            </Button>
          </>
        }
      />

      <div className="grid gap-3 px-6 py-4 sm:grid-cols-3">
        <StatCard label="Total entries" value={status?.total_entries ?? 0} />
        <StatCard
          label="By subject"
          value={
            Object.entries(status?.by_subject ?? {})
              .map(([k, v]) => `${k.toUpperCase()} ${v}`)
              .join(" · ") || "—"
          }
          small
        />
        <StatCard
          label="Stale"
          value={Object.values(status?.stale_by_subject ?? {}).reduce((a, b) => a + b, 0)}
          tone="warn"
        />
      </div>

      <div className="flex flex-wrap items-center gap-2 px-6">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by qid…"
            className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-sm outline-none focus:border-primary"
          />
        </div>
        <Segmented
          value={subject}
          onChange={setSubject}
          options={[
            { value: "all", label: "All" },
            ...subjectOptions
              .filter((s) => s !== "all")
              .map((s) => ({ value: s, label: s.toUpperCase() })),
          ]}
        />
        <button
          onClick={() => setStaleOnly((v) => !v)}
          className={cn(
            "inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm text-muted-foreground transition-colors hover:text-foreground",
            staleOnly && "border-warning/50 bg-warning/10 text-warning",
          )}
        >
          <Filter className="h-3.5 w-3.5" /> Stale only
        </button>
      </div>

      <div className="p-6">
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-background/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">QID</th>
                <th className="px-4 py-3 font-medium">Subject</th>
                <th className="px-4 py-3 text-right font-medium">Score</th>
                <th className="px-4 py-3 text-right font-medium">Words</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Cached</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {filtered?.map((e) => (
                <tr
                  key={e.qid}
                  className={cn(
                    "border-t border-border transition-colors hover:bg-background/40",
                    e.is_stale && "bg-warning/5",
                  )}
                >
                  <td className="px-4 py-3 font-mono text-[12px]">{e.qid}</td>
                  <td className="px-4 py-3">
                    <StatusBadge tone="primary">{e.subject.toUpperCase()}</StatusBadge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    {e.validation_score != null ? Math.round(e.validation_score * 100) : "—"}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-muted-foreground">
                    {e.target_word_count}
                  </td>
                  <td className="px-4 py-3">
                    {e.is_stale ? (
                      <StatusBadge tone="warn">stale · {e.stale_reasons[0]}</StatusBadge>
                    ) : (
                      <StatusBadge tone="pass">fresh</StatusBadge>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatTimestamp(e.cached_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() =>
                        api
                          .getCacheEntry(e.qid)
                          .then((entry) => {
                            const text = entry.answer_text;
                            const blob = new Blob([text], { type: "text/plain" });
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement("a");
                            a.href = url;
                            a.download = `medrack-${e.qid}.txt`;
                            a.click();
                            URL.revokeObjectURL(url);
                          })
                          .catch((err: Error) =>
                            alert(`Cache entry download failed: ${err.message}`),
                          )
                      }
                    >
                      View
                    </Button>
                  </td>
                </tr>
              ))}
              {!isLoading && filtered && filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-sm text-muted-foreground">
                    No cache entries match the current filters.
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

function StatCard({
  label,
  value,
  tone,
  small,
}: {
  label: string;
  value: string | number;
  tone?: "warn";
  small?: boolean;
}) {
  return (
    <div
      className={cn("surface-card px-4 py-3", tone === "warn" && "border-warning/30 bg-warning/5")}
    >
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div
        className={cn(
          "mt-1 font-display font-semibold tabular-nums",
          small ? "text-base" : "text-2xl",
        )}
      >
        {value}
      </div>
    </div>
  );
}

function Segmented<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="inline-flex h-9 rounded-md border border-border bg-background p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-[5px] px-3 text-sm font-medium text-muted-foreground transition-colors",
            value === o.value && "bg-primary/15 text-primary",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
