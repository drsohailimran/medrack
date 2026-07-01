import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/api";

const VARIANTS = {
  pass: "bg-success/15 text-success ring-success/30",
  warn: "bg-warning/15 text-warning ring-warning/30",
  fail: "bg-destructive/15 text-destructive ring-destructive/30",
  info: "bg-muted text-muted-foreground ring-border",
  primary: "bg-primary/15 text-primary ring-primary/30",
} as const;

export type StatusTone = keyof typeof VARIANTS;

export function StatusBadge({
  tone = "info",
  children,
  className,
}: {
  tone?: StatusTone | Severity;
  children: React.ReactNode;
  className?: string;
}) {
  const v = (tone in VARIANTS ? tone : "info") as StatusTone;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset",
        VARIANTS[v],
        className,
      )}
    >
      {children}
    </span>
  );
}
