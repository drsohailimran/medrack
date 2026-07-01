import { useId, useState } from "react";
import { ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export function JsonTree({ value, depth = 0 }: { value: unknown; depth?: number }) {
  if (value === null) return <span className="text-muted-foreground">null</span>;
  if (typeof value === "boolean") return <span className="text-chart-2">{String(value)}</span>;
  if (typeof value === "number") return <span className="text-chart-3">{value}</span>;
  if (typeof value === "string") return <span className="text-success">&quot;{value}&quot;</span>;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">[]</span>;
    return (
      <Collapsible label={`Array(${value.length})`} depth={depth}>
        {value.map((v, i) => (
          <div key={i} className="flex gap-2">
            <span className="select-none text-muted-foreground">{i}</span>
            <JsonTree value={v} depth={depth + 1} />
          </div>
        ))}
      </Collapsible>
    );
  }

  if (isObj(value)) {
    const keys = Object.keys(value);
    if (keys.length === 0) return <span className="text-muted-foreground">{`{}`}</span>;
    return (
      <Collapsible label={`Object · ${keys.length} keys`} depth={depth}>
        {keys.map((k) => (
          <div key={k} className="flex gap-2">
            <span className="select-none text-chart-2">{k}:</span>
            <JsonTree value={(value as Record<string, unknown>)[k]} depth={depth + 1} />
          </div>
        ))}
      </Collapsible>
    );
  }

  return <span>{String(value)}</span>;
}

function Collapsible({
  label,
  children,
  depth,
}: {
  label: string;
  children: React.ReactNode;
  depth: number;
}) {
  const [open, setOpen] = useState(depth < 1);
  const id = useId();
  return (
    <div className="font-mono text-[12px]">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1 rounded text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("h-3 w-3 transition-transform", open && "rotate-90")} />
        <span className="text-[11px]">{label}</span>
      </button>
      {open && (
        <div id={id} className="ml-3 border-l border-border/70 pl-3">
          {children}
        </div>
      )}
    </div>
  );
}
