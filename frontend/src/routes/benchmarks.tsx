import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { ArrowDownRight, ArrowUpRight, GitCompare, LineChart, Zap } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatTimestamp } from "@/lib/format";

export const Route = createFileRoute("/benchmarks")({
  head: () => ({ meta: [{ title: "Benchmarks — MedRack" }] }),
  component: BenchmarksPage,
});

function BenchmarksPage() {
  const { data: runs } = useQuery({
    queryKey: ["benchmarks"],
    queryFn: () => api.listBenchmarkRuns(),
  });
  const [selected, setSelected] = useState<string[]>([]);

  const toggle = (id: string) =>
    setSelected((sel) =>
      sel.includes(id) ? sel.filter((x) => x !== id) : sel.length < 2 ? [...sel, id] : [sel[1], id],
    );

  const { data: compare } = useQuery({
    queryKey: ["benchmark-compare", selected],
    queryFn: () => api.compareBenchmarks(selected[0], selected[1]),
    enabled: selected.length === 2,
  });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Benchmarks"
        description="Past pipeline runs across the regression dataset. Compare two runs to see token, latency, and cache deltas."
        actions={
          <Button
            disabled={selected.length !== 2}
            onClick={() => {
              if (selected.length === 2) {
                api.compareBenchmarks(selected[0], selected[1]).catch(() => {});
              }
            }}
          >
            <GitCompare className="mr-1.5 h-4 w-4" /> Compare {selected.length}/2
          </Button>
        }
      />

      <div className="grid gap-4 px-6 py-4 sm:grid-cols-4">
        <Kpi
          label="Latest avg latency"
          value={runs?.[0] ? `${runs[0].avg_total_latency_seconds.toFixed(2)}s` : "—"}
          icon={LineChart}
        />
        <Kpi
          label="Latest cache hit"
          value={runs?.[0] ? `${Math.round(runs[0].cache_hit_rate * 100)}%` : "—"}
          icon={Zap}
        />
        <Kpi
          label="Latest tokens"
          value={runs?.[0] ? runs[0].total_tokens.toLocaleString() : "—"}
        />
        <Kpi label="Runs stored" value={runs?.length ?? 0} />
      </div>

      <div className="p-6">
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <table className="w-full text-sm">
            <thead className="bg-background/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="w-10 px-3 py-3" />
                <th className="px-4 py-3 font-medium">Run</th>
                <th className="px-4 py-3 font-medium">Mode</th>
                <th className="px-4 py-3 text-right font-medium">Questions</th>
                <th className="px-4 py-3 text-right font-medium">Success</th>
                <th className="px-4 py-3 text-right font-medium">Cache hit</th>
                <th className="px-4 py-3 text-right font-medium">Tokens</th>
                <th className="px-4 py-3 text-right font-medium">Avg latency</th>
              </tr>
            </thead>
            <tbody>
              {runs?.map((r) => (
                <tr
                  key={r.run_id}
                  className={cn(
                    "border-t border-border",
                    selected.includes(r.run_id) && "bg-primary/5",
                  )}
                >
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      checked={selected.includes(r.run_id)}
                      onChange={() => toggle(r.run_id)}
                      className="h-3.5 w-3.5 accent-primary"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-mono text-[12px] text-foreground">{r.run_id}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {formatTimestamp(r.timestamp)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge tone={r.llm_mode === "real" ? "primary" : "info"}>
                      {r.llm_mode}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">{r.n_questions}</td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    {Math.round((r.n_success / Math.max(1, r.n_success + r.n_failure)) * 100)}%
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      ({r.n_success}/{r.n_success + r.n_failure})
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-success">
                    {Math.round(r.cache_hit_rate * 100)}%
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums text-muted-foreground">
                    {r.total_tokens.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right font-mono tabular-nums">
                    {r.avg_total_latency_seconds.toFixed(2)}s
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {compare && (
          <div className="surface-card mt-6 p-5">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                  Comparison
                </div>
                <div className="font-display text-base font-semibold">
                  {compare.run_a} <span className="text-muted-foreground">→</span> {compare.run_b}
                </div>
              </div>
              <StatusBadge tone="primary">delta</StatusBadge>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {Object.entries(compare.delta).map(([k, v]) => {
                const positive = v > 0;
                const negative = v < 0;
                const isLatency =
                  k.includes("latency") || k.includes("tokens") || k === "n_failure";
                const good = isLatency ? negative : positive;
                return (
                  <div key={k} className="rounded-md border border-border bg-background px-3 py-2">
                    <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      {k}
                    </div>
                    <div
                      className={cn(
                        "mt-0.5 flex items-center gap-1 font-mono text-sm font-semibold tabular-nums",
                        v === 0 && "text-muted-foreground",
                        v !== 0 && good && "text-success",
                        v !== 0 && !good && "text-destructive",
                      )}
                    >
                      {positive && <ArrowUpRight className="h-3.5 w-3.5" />}
                      {negative && <ArrowDownRight className="h-3.5 w-3.5" />}
                      {typeof v === "number" ? (Number.isInteger(v) ? v : v.toFixed(2)) : v}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

function Kpi({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon?: typeof LineChart;
}) {
  return (
    <div className="surface-card flex items-center gap-3 px-4 py-3">
      {Icon && (
        <div className="grid h-9 w-9 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20">
          <Icon className="h-4 w-4" />
        </div>
      )}
      <div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
        <div className="font-display text-xl font-semibold tabular-nums">{value}</div>
      </div>
    </div>
  );
}
