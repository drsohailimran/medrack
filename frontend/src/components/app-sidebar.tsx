import { Link, useRouterState } from "@tanstack/react-router";
import { BookOpen, Database, Library, ScrollText, Settings, Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

type NavItem = { to: string; label: string; icon: typeof BookOpen; section?: string; kbd?: string };

const nav: NavItem[] = [
  { to: "/", label: "Workspace", icon: Sparkles, kbd: "G" },
  { to: "/books", label: "Books", icon: BookOpen, section: "Library" },
  { to: "/question-banks", label: "Question Banks", icon: Library },
  { to: "/answers", label: "Cached Answers", icon: Database, section: "Operations" },
  { to: "/logs", label: "Logs", icon: ScrollText },
  { to: "/settings", label: "Settings", icon: Settings, section: "System" },
];

export function AppSidebar() {
  return (
    <aside className="hidden h-dvh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex">
      <SidebarBody />
    </aside>
  );
}

// The sidebar contents, shared by the static desktop sidebar and the mobile
// drawer. `onNavigate` (used by the drawer) closes the drawer after a tap.
export function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const { data: version } = useQuery({
    queryKey: ["version"],
    queryFn: () => api.getVersion(),
    refetchInterval: 30_000,
    retry: false,
  });

  const apiBase =
    (import.meta.env.VITE_MEDRACK_API_BASE as string | undefined) ?? "http://localhost:8000/api/v1";
  const apiHost = (() => {
    try {
      return new URL(apiBase).host;
    } catch {
      return apiBase;
    }
  })();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center gap-2 px-4">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/30">
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M4 4h6v6H4z" />
            <path d="M14 4h6v6h-6z" />
            <path d="M4 14h6v6H4z" />
            <path d="M14 14h6v6h-6z" />
          </svg>
        </div>
        <div className="leading-tight">
          <div className="text-[13px] font-semibold tracking-tight">MedRack</div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
            Authoring
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-4 pt-2 text-sm">
        {nav.map((item, i) => {
          const Icon = item.icon;
          const active = pathname === item.to || (item.to !== "/" && pathname.startsWith(item.to));
          return (
            <div key={item.to}>
              {item.section && (
                <div className="mt-4 px-2 pb-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70">
                  {item.section}
                </div>
              )}
              <Link
                to={item.to}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sidebar-foreground/85 transition-colors",
                  "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                  active && "bg-sidebar-accent text-sidebar-accent-foreground",
                )}
              >
                {active && (
                  <span className="absolute inset-y-1 left-0 w-0.5 rounded-r bg-primary" />
                )}
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
                  )}
                />
                <span className="truncate">{item.label}</span>
                {item.kbd && (
                  <kbd className="ml-auto hidden rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground group-hover:inline-block">
                    {item.kbd}
                  </kbd>
                )}
              </Link>
            </div>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-2 rounded-md bg-sidebar-accent/50 px-2.5 py-2">
          <div
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              version ? "bg-success shadow-[0_0_8px] shadow-success/70" : "bg-warning",
            )}
          />
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-[11px] font-medium">
              {version ? "Backend online" : "Backend offline"}
            </div>
            <div className="truncate text-[10px] text-muted-foreground">
              {apiHost} · v{version?.package_version ?? "—"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
