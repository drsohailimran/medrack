import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { FolderKanban, Plus } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Project } from "@/lib/api";

export const Route = createFileRoute("/projects")({
  head: () => ({ meta: [{ title: "Projects — MedRack" }] }),
  component: ProjectsPage,
});

const SAMPLE_PROJECTS = [
  {
    id: "psm-3rd-year",
    name: "PSM · 3rd Year",
    subject: "psm",
    description: "Community Medicine exam prep for the third-year MBBS block.",
    question_count: 18,
    created_at: "2026-06-15T00:00:00Z",
    updated_at: "2026-06-30T00:00:00Z",
  },
  {
    id: "fmt-finals",
    name: "FMT · Finals",
    subject: "fmt",
    description: "Forensic Medicine & Toxicology revision block for the final-year exam.",
    question_count: 12,
    created_at: "2026-06-20T00:00:00Z",
    updated_at: "2026-06-29T00:00:00Z",
  },
] as const;

function ProjectsPage() {
  // Projects are a frontend-only abstraction — the backend stores by
  // subject + module, not by named project. We show the list (still useful
  // for grouping UI state) but clearly mark each entry as a local
  // grouping, not a backend resource.
  const { data: books } = useQuery({ queryKey: ["books"], queryFn: () => api.listBooks() });
  const [openNew, setOpenNew] = useState(false);
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("psm");
  const [description, setDescription] = useState("");
  const [projects, setProjects] = useState<Project[]>(() => SAMPLE_PROJECTS.map((p) => ({ ...p })));

  const create = () => {
    if (!name.trim()) return;
    const now = new Date().toISOString();
    setProjects((cur) => [
      ...cur,
      {
        id: name
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-|-$/g, ""),
        name,
        subject,
        description: description || "Local project grouping.",
        question_count: 0,
        created_at: now,
        updated_at: now,
      },
    ]);
    setName("");
    setDescription("");
    setOpenNew(false);
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Workspace"
        title="Projects"
        description="Local groupings of related questions. The backend stores by subject + module, not by named project — projects are a frontend-only convenience."
        actions={
          <Button onClick={() => setOpenNew(true)}>
            <Plus className="mr-1.5 h-4 w-4" /> New project
          </Button>
        }
      />
      <div className="px-6 py-3 text-[11px] text-muted-foreground">
        Available subjects from imported books:{" "}
        {Array.from(new Set(books?.map((b) => b.subject) ?? [])).join(", ") || "—"}
      </div>
      <div className="grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3">
        {projects.map((p) => (
          <div
            key={p.id}
            className="surface-card flex flex-col gap-3 p-5 transition-colors hover:bg-surface-2"
          >
            <div className="flex items-start justify-between">
              <div className="grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20">
                <FolderKanban className="h-5 w-5" />
              </div>
              <StatusBadge tone="primary">{p.subject.toUpperCase()}</StatusBadge>
            </div>
            <div>
              <div className="font-display text-base font-semibold tracking-tight">{p.name}</div>
              <p className="mt-1 text-xs text-muted-foreground">{p.description}</p>
            </div>
            <div className="mt-auto flex items-center justify-between border-t border-border pt-3 text-[11px] text-muted-foreground">
              <span>
                <span className="font-mono text-foreground">{p.question_count}</span> questions
              </span>
              <span>Updated {new Date(p.updated_at).toLocaleDateString()}</span>
            </div>
          </div>
        ))}
      </div>

      {openNew && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="surface-card w-full max-w-md p-6">
            <h2 className="text-lg font-semibold">New project</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Projects are saved locally in this browser. They are not synced to the backend. Use
              subjects to organize work on the server.
            </p>
            <div className="mt-4 space-y-3 text-sm">
              <label className="block">
                <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Name
                </span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Surgery · Block 4"
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Subject
                </span>
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </label>
              <label className="block">
                <span className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Description (optional)
                </span>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full rounded-md border border-border bg-background px-3 py-2"
                />
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => setOpenNew(false)}>
                Cancel
              </Button>
              <Button onClick={create} disabled={!name.trim()}>
                Create
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
