import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Search } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { api } from "@/lib/api";
import type { LogName } from "@/lib/api";
import { cn } from "@/lib/utils";

const TABS: LogName[] = ["ingestion", "generation", "validation", "benchmark"];

export const Route = createFileRoute("/logs")({
  head: () => ({ meta: [{ title: "Logs — MedRack" }] }),
  component: LogsPage,
});

function LogsPage() {
  const [tab, setTab] = useState<LogName>("generation");
  const [query, setQuery] = useState("");

  const { data: entries } = useQuery({
    queryKey: ["logs", tab, query],
    queryFn: () => (query ? api.searchLog(tab, query) : api.tailLog(tab)),
  });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Logs"
        description="Rolling tail of backend log files."
      />
      <div className="flex items-center justify-between gap-3 border-b border-border px-6">
        <div className="flex">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                "relative px-4 py-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground",
                tab === t && "text-foreground",
              )}
            >
              {t[0].toUpperCase() + t.slice(1)}
              {tab === t && (
                <span className="absolute inset-x-3 -bottom-px h-0.5 rounded bg-primary" />
              )}
            </button>
          ))}
        </div>
        <div className="relative w-72">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search…"
            className="h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-sm outline-none focus:border-primary"
          />
        </div>
      </div>
      <div className="p-6">
        <div className="overflow-hidden rounded-lg border border-border bg-[oklch(0.13_0.012_250)] font-mono text-[12px]">
          {entries?.map((entry, i) => (
            <div
              key={i}
              className="grid grid-cols-[auto_1fr] gap-3 border-b border-border/40 px-4 py-2 last:border-0 hover:bg-accent/20"
            >
              <span className="select-none text-muted-foreground">
                {String(i + 1).padStart(3, "0")}
              </span>
              <span className="whitespace-pre-wrap break-all text-foreground/90">
                {Object.entries(entry).map(([k, v]) => (
                  <span key={k} className="mr-3">
                    <span className="text-chart-2">{k}=</span>
                    <span className={typeof v === "string" ? "text-success" : "text-chart-3"}>
                      {typeof v === "string" ? `"${v}"` : String(v)}
                    </span>
                  </span>
                ))}
              </span>
            </div>
          ))}
          {entries && entries.length === 0 && (
            <div className="px-4 py-10 text-center text-muted-foreground">
              No log entries match.
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
