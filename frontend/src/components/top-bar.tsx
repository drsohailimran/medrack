import { useQuery } from "@tanstack/react-query";
import { Command, HelpCircle, Menu, Search } from "lucide-react";
import { api } from "@/lib/api";

export function TopBar({ onMenuClick }: { onMenuClick?: () => void }) {
  const { data: version } = useQuery({ queryKey: ["version"], queryFn: () => api.getVersion() });

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:gap-3 sm:px-4">
      {/* Hamburger — opens the nav drawer on mobile */}
      <button
        onClick={onMenuClick}
        className="grid h-9 w-9 shrink-0 place-items-center rounded-md border border-border bg-surface text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground md:hidden"
        aria-label="Open navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex min-w-0 flex-1 items-center gap-2">
        <button
          className="group inline-flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-border bg-surface px-3 text-left text-sm text-muted-foreground transition-colors hover:border-border hover:bg-surface-2"
          aria-label="Open command palette"
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">Search questions, books, runs…</span>
          <kbd className="ml-auto hidden items-center gap-0.5 rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] font-medium sm:flex">
            <Command className="h-3 w-3" /> K
          </kbd>
        </button>
      </div>

      <div className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
        <span className="hidden rounded-md border border-border bg-surface px-2 py-1 font-mono text-[10px] md:inline-flex">
          {version ? `v${version.package_version}` : "v—"}
        </span>
        <button className="grid h-8 w-8 place-items-center rounded-md border border-border bg-surface text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground">
          <HelpCircle className="h-4 w-4" />
        </button>
      </div>
    </header>
  );
}
