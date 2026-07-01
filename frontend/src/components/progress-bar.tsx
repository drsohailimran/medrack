import { cn } from "@/lib/utils";

// A thin progress bar that always shows the percentage to two decimals
// (e.g. "9.21%"), per the operator's request.
export function ProgressBar({
  percent,
  label,
  error,
  className,
}: {
  percent: number;
  label?: string;
  error?: string | null;
  className?: string;
}) {
  const p = Math.max(0, Math.min(100, Number.isFinite(percent) ? percent : 0));
  return (
    <div className={cn("w-full", className)}>
      <div className="mb-1 flex items-center justify-between gap-2 text-[11px]">
        <span className="truncate text-muted-foreground">{label}</span>
        <span
          className={cn(
            "font-mono tabular-nums",
            error ? "text-destructive" : "text-foreground",
          )}
        >
          {p.toFixed(2)}%
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-300",
            error ? "bg-destructive" : "bg-primary",
          )}
          style={{ width: `${p}%` }}
        />
      </div>
      {error ? <p className="mt-1 text-[11px] text-destructive">{error}</p> : null}
    </div>
  );
}
