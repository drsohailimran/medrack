import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { o as Search } from "../_libs/lucide-react.mjs";
import { n as api, r as cn, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/logs-at6Ekqme.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var TABS = [
	"ingestion",
	"generation",
	"validation",
	"benchmark"
];
function LogsPage() {
	const [tab, setTab] = (0, import_react.useState)("generation");
	const [query, setQuery] = (0, import_react.useState)("");
	const { data: entries } = useQuery({
		queryKey: [
			"logs",
			tab,
			query
		],
		queryFn: () => query ? api.searchLog(tab, query) : api.tailLog(tab)
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Operations",
			title: "Logs",
			description: "Rolling tail of backend log files."
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "flex items-center justify-between gap-3 border-b border-border px-6",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "flex",
				children: TABS.map((t) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
					onClick: () => setTab(t),
					className: cn("relative px-4 py-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground", tab === t && "text-foreground"),
					children: [t[0].toUpperCase() + t.slice(1), tab === t && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { className: "absolute inset-x-3 -bottom-px h-0.5 rounded bg-primary" })]
				}, t))
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "relative w-72",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Search, { className: "pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
					value: query,
					onChange: (e) => setQuery(e.target.value),
					placeholder: "Search…",
					className: "h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-sm outline-none focus:border-primary"
				})]
			})]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "p-6",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "overflow-hidden rounded-lg border border-border bg-[oklch(0.13_0.012_250)] font-mono text-[12px]",
				children: [entries?.map((entry, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "grid grid-cols-[auto_1fr] gap-3 border-b border-border/40 px-4 py-2 last:border-0 hover:bg-accent/20",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "select-none text-muted-foreground",
						children: String(i + 1).padStart(3, "0")
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
						className: "whitespace-pre-wrap break-all text-foreground/90",
						children: Object.entries(entry).map(([k, v]) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
							className: "mr-3",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
								className: "text-chart-2",
								children: [k, "="]
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: typeof v === "string" ? "text-success" : "text-chart-3",
								children: typeof v === "string" ? `"${v}"` : String(v)
							})]
						}, k))
					})]
				}, i)), entries && entries.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "px-4 py-10 text-center text-muted-foreground",
					children: "No log entries match."
				})]
			})
		})
	] });
}
//#endregion
export { LogsPage as component };
