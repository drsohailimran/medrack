// Shared primitives used by multiple route components.
//
// These were extracted to remove duplication between src/routes/*.tsx
// during the Frontend Review & Polish pass. Behavior is identical
// to the inline versions; this is purely a consolidation.

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </span>
      {children}
    </label>
  );
}

export function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "warn";
}) {
  return (
    <div
      className={cn(
        "rounded-md border border-border bg-surface px-3 py-2",
        tone === "warn" && "border-warning/30 bg-warning/5",
      )}
    >
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-mono text-sm font-semibold tabular-nums">{value}</div>
    </div>
  );
}
