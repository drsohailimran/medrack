import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileText,
  Play,
  ShieldAlert,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useState } from "react";
import type { Severity, ValidationReport } from "@/lib/api";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./status-badge";
import { Button } from "./ui/button";

const SEVERITY_ICON: Record<Severity, React.FC<{ className?: string }>> = {
  pass: CheckCircle2,
  warn: ShieldAlert,
  fail: XCircle,
};

export function ValidationPanel({
  report,
  wordCount,
  tokenCount,
  loading,
  pending,
  onValidate,
}: {
  report?: ValidationReport;
  wordCount?: number;
  tokenCount?: number;
  loading?: boolean;
  pending?: boolean;
  onValidate?: () => void;
}) {
  if (loading) {
    return (
      <div className="space-y-2 p-4">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="h-9 animate-pulse rounded-md bg-muted/40" />
        ))}
      </div>
    );
  }
  if (!report) {
    return (
      <div className="px-4 py-6">
        <p className="text-xs text-muted-foreground">
          Validation results appear after an answer is generated. Run the 9-rule suite against the
          current answer to populate this panel.
        </p>
        {onValidate && (
          <Button
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={onValidate}
            disabled={pending}
          >
            <Play className="mr-1.5 h-3.5 w-3.5" />
            {pending ? "Running…" : "Run validation"}
          </Button>
        )}
      </div>
    );
  }

  const passCount = report.results.filter((r) => r.severity === "pass").length;
  const total = report.results.length;
  const scorePct = Math.round(report.score * 100);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Validation
            </div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              {report.pass ? (
                <ShieldCheck className="h-4 w-4 text-success" />
              ) : (
                <ShieldAlert className="h-4 w-4 text-warning" />
              )}
              {report.pass ? "Passed" : "Action required"}
            </div>
          </div>
          <div className="text-right">
            <div className="font-mono text-2xl font-semibold tabular-nums text-foreground">
              {scorePct}
              <span className="ml-0.5 text-xs text-muted-foreground">/100</span>
            </div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
              {passCount}/{total} rules pass
            </div>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <Metric label="Words" value={wordCount?.toLocaleString() ?? "—"} />
          <Metric label="Tokens" value={tokenCount?.toLocaleString() ?? "—"} />
        </div>
        {onValidate && (
          <div className="mt-3">
            <Button size="sm" variant="outline" onClick={onValidate} disabled={pending}>
              <Play className="mr-1.5 h-3.5 w-3.5" />
              {pending ? "Running…" : "Re-run validation"}
            </Button>
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {report.results.map((r) => (
          <RuleRow key={r.rule_name} rule={r} />
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-surface px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="font-mono text-sm font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function RuleRow({ rule }: { rule: ValidationReport["results"][number] }) {
  const [open, setOpen] = useState(false);
  const Icon = SEVERITY_ICON[rule.severity];
  const hasDetails = !!rule.details && Object.keys(rule.details).length > 0;

  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={() => hasDetails && setOpen((v) => !v)}
        className={cn(
          "flex w-full items-start gap-3 px-4 py-2.5 text-left",
          hasDetails && "hover:bg-accent/30",
        )}
      >
        <Icon
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0",
            rule.severity === "pass" && "text-success",
            rule.severity === "warn" && "text-warning",
            rule.severity === "fail" && "text-destructive",
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[12px] font-medium text-foreground">
              {rule.rule_name}
            </span>
            <StatusBadge tone={rule.severity}>{rule.severity}</StatusBadge>
          </div>
          <div className="truncate text-[11px] text-muted-foreground">{rule.message}</div>
        </div>
        {hasDetails &&
          (open ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          ))}
      </button>
      {open && hasDetails && (
        <div className="bg-background/60 px-4 pb-3 pt-1 text-[11px]">
          <pre className="overflow-auto rounded border border-border bg-surface p-2 font-mono text-[11px] text-muted-foreground">
            {JSON.stringify(rule.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export function ValidationFooter() {
  return (
    <div className="flex items-center gap-2 border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
      <FileText className="h-3 w-3" /> 9 rules from the FROZEN validation suite
    </div>
  );
}
