import { useState } from "react";
import { ChevronDown, Clock, Play } from "lucide-react";
import type { PipelineStageOutput, PipelineTrace } from "@/lib/api";
import { cn } from "@/lib/utils";
import { JsonTree } from "./json-tree";
import { Button } from "./ui/button";

const STAGE_META: Record<string, { label: string; hint: string }> = {
  planner: { label: "Planner", hint: "Deterministic blueprint of sections & word allocations" },
  blueprint: { label: "Blueprint", hint: "Retrieval-aware enrichment of the planner output" },
  retrieval: { label: "Retrieval", hint: "Adaptive vector search over book chunks" },
  reranker: { label: "Reranker", hint: "Re-orders evidence by semantic relevance" },
  writer: { label: "Writer", hint: "Synthesizes prose from blueprint + evidence" },
  validator: { label: "Validator", hint: "Runs 9 quality rules against the answer" },
};

export function PipelinePanel({
  trace,
  loading,
  onInspect,
}: {
  trace?: PipelineTrace;
  loading?: boolean;
  onInspect?: () => void;
}) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
            Pipeline
          </div>
          <div className="text-sm font-semibold">Trace</div>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right text-[11px] text-muted-foreground">
            {trace ? (
              <>
                <div>Total {trace.total_latency_seconds.toFixed(3)}s</div>
                <div className="font-mono">{trace.qid}</div>
              </>
            ) : (
              <div>—</div>
            )}
          </div>
          {onInspect && (
            <Button size="sm" variant="outline" onClick={onInspect} disabled={loading}>
              <Play className="mr-1.5 h-3.5 w-3.5" />
              Inspect
            </Button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {!trace && !loading && (
          <div className="px-4 py-6 text-xs text-muted-foreground">
            Generate or inspect a question to populate pipeline stages.
          </div>
        )}
        {loading && (
          <div className="space-y-2 p-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-9 animate-pulse rounded-md bg-muted/40" />
            ))}
          </div>
        )}
        {trace?.stages.map((stage, i) => (
          <Stage key={stage.stage} stage={stage} index={i + 1} defaultOpen={i < 2} />
        ))}
      </div>
    </div>
  );
}

function Stage({
  stage,
  index,
  defaultOpen,
}: {
  stage: PipelineStageOutput;
  index: number;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(!!defaultOpen);
  const meta = STAGE_META[stage.stage] ?? { label: stage.stage, hint: "" };

  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-accent/40",
          open && "bg-accent/30",
        )}
      >
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary/10 font-mono text-[10px] text-primary ring-1 ring-primary/30">
          {index}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-[13px] font-medium">
            {meta.label}
            <span className="rounded-full bg-success/10 px-1.5 py-0.5 text-[9px] font-medium text-success ring-1 ring-inset ring-success/20">
              ok
            </span>
          </div>
          <div className="truncate text-[11px] text-muted-foreground">{meta.hint}</div>
        </div>
        <span className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground">
          <Clock className="h-3 w-3" />
          {stage.latency_seconds.toFixed(3)}s
        </span>
        <ChevronDown
          className={cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <div className="bg-background/60 px-5 py-3">
          <JsonTree value={stage.output} />
        </div>
      )}
    </div>
  );
}
