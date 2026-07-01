import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { api } from "@/lib/api";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — MedRack" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const { data: v } = useQuery({ queryKey: ["version"], queryFn: () => api.getVersion() });

  return (
    <AppShell>
      <PageHeader
        eyebrow="System"
        title="Settings"
        description="Backend version, pipeline versions, and frontend preferences."
      />
      <div className="grid gap-6 p-6 lg:grid-cols-2">
        <section className="surface-card p-5">
          <h2 className="font-display text-base font-semibold tracking-tight">Backend</h2>
          <div className="mt-4 space-y-3 text-sm">
            <Row
              label="Package version"
              value={<span className="font-mono">{v?.package_version ?? "—"}</span>}
            />
            <Row
              label="Schema version"
              value={<span className="font-mono">{v?.schema_version ?? "—"}</span>}
            />
            <Row
              label="Benchmark baseline"
              value={
                v?.benchmark_baseline_tag ? (
                  <StatusBadge tone="primary">{v.benchmark_baseline_tag}</StatusBadge>
                ) : (
                  "—"
                )
              }
            />
            <Row
              label="API base"
              value={
                <span className="font-mono text-muted-foreground">
                  {import.meta.env.VITE_MEDRACK_API_BASE ?? "http://localhost:8000/api/v1"}
                </span>
              }
            />
          </div>
        </section>

        <section className="surface-card p-5">
          <h2 className="font-display text-base font-semibold tracking-tight">Pipeline versions</h2>
          <table className="mt-4 w-full text-sm">
            <tbody>
              {v &&
                Object.entries(v.pipeline_versions).map(([k, val]) => (
                  <tr key={k} className="border-t border-border first:border-0">
                    <td className="py-2 capitalize text-muted-foreground">{k}</td>
                    <td className="py-2 text-right font-mono tabular-nums">{val}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </section>

        <section className="surface-card p-5 lg:col-span-2">
          <h2 className="font-display text-base font-semibold tracking-tight">
            Frontend preferences
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Purely client-side — never sent to the backend.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <Pref label="Theme" value="Dark" />
            <Pref label="Default subject" value="PSM" />
            <Pref label="Default marks" value="10" />
            <Pref label="Polling interval" value="5s" />
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-t border-border pt-2 first:border-0 first:pt-0">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Pref({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-background px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 font-display text-base font-semibold">{value}</div>
    </div>
  );
}
