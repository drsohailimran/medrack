import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Play } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { PipelinePanel } from "@/components/pipeline-panel";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/primitives";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { Marks, Subject } from "@/lib/api";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/pipeline")({
  head: () => ({ meta: [{ title: "Pipeline Inspector — MedRack" }] }),
  component: PipelinePage,
});

function PipelinePage() {
  const [qid, setQid] = useState("q001");
  const [question, setQuestion] = useState("Discuss the management of diabetes mellitus.");
  const [subject, setSubject] = useState<Subject>("psm");
  const [marks, setMarks] = useState<Marks>(10);
  const [submitted, setSubmitted] = useState(true);

  const {
    data: trace,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["inspect", qid, question, subject, marks, submitted],
    queryFn: () => api.inspectPipeline({ qid, question_text: question, subject, marks }),
    enabled: submitted,
  });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Operations"
        title="Pipeline Inspector"
        description="Read-only trace of all six pipeline stages for a given question. Useful when verifying blueprints and retrieval configuration."
      />

      <div className="grid h-[calc(100%-7.5rem)] grid-cols-1 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
        <aside className="space-y-4 border-r border-border p-6">
          <Field label="QID">
            <input
              value={qid}
              onChange={(e) => setQid(e.target.value)}
              className="h-9 w-full rounded-md border border-border bg-background px-3 font-mono text-sm outline-none focus:border-primary"
            />
          </Field>
          <Field label="Question text">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              className="min-h-[140px] bg-background"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Subject">
              <Seg
                value={subject}
                onChange={(v) => setSubject(v as Subject)}
                options={[
                  { value: "psm", label: "PSM" },
                  { value: "fmt", label: "FMT" },
                ]}
              />
            </Field>
            <Field label="Marks">
              <Seg
                value={String(marks)}
                onChange={(v) => setMarks(Number(v) as Marks)}
                options={[
                  { value: "5", label: "5" },
                  { value: "10", label: "10" },
                  { value: "15", label: "15" },
                ]}
              />
            </Field>
          </div>
          <Button
            onClick={() => {
              setSubmitted(true);
              refetch();
            }}
            className="w-full"
          >
            <Play className="mr-2 h-4 w-4" /> Inspect pipeline
          </Button>
          <p className="text-[11px] text-muted-foreground">
            This call does not trigger generation. It returns each stage's configuration and
            reported latency.
          </p>
        </aside>
        <div className="min-h-0 overflow-hidden">
          <PipelinePanel trace={trace} loading={isFetching} />
        </div>
      </div>
    </AppShell>
  );
}

function Seg<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="grid grid-flow-col rounded-md border border-border bg-background p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded px-2 py-1 text-[12px] font-medium text-muted-foreground transition-colors",
            value === o.value && "bg-primary/15 text-primary ring-1 ring-inset ring-primary/30",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
