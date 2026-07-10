import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, i as useQueryClient, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { A as Funnel, l as RefreshCw, o as Search, y as Download } from "../_libs/lucide-react.mjs";
import { n as api, r as cn, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
import { n as formatTimestamp } from "./format-BX-FBxQr.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/history-DS_s13Q8.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function HistoryPage() {
	const [subject, setSubject] = (0, import_react.useState)("all");
	const [staleOnly, setStaleOnly] = (0, import_react.useState)(false);
	const [query, setQuery] = (0, import_react.useState)("");
	const qc = useQueryClient();
	const { data: status } = useQuery({
		queryKey: ["cache-status"],
		queryFn: () => api.getCacheStatus()
	});
	const { data: entries, isLoading } = useQuery({
		queryKey: [
			"cache-entries",
			subject,
			staleOnly
		],
		queryFn: () => api.listCacheEntries({
			subject: subject === "all" ? void 0 : subject,
			stale_only: staleOnly
		})
	});
	const subjectOptions = (0, import_react.useMemo)(() => {
		const set = /* @__PURE__ */ new Set(["all"]);
		entries?.forEach((e) => set.add(e.subject));
		return Array.from(set);
	}, [entries]);
	const refresh = () => {
		qc.invalidateQueries({ queryKey: ["cache-entries"] });
		qc.invalidateQueries({ queryKey: ["cache-status"] });
	};
	const exportJson = () => {
		if (!entries || entries.length === 0) return;
		const blob = new Blob([JSON.stringify(entries, null, 2)], { type: "application/json" });
		const url = URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;
		a.download = `medrack-cache-${(/* @__PURE__ */ new Date()).toISOString().slice(0, 10)}.json`;
		a.click();
		URL.revokeObjectURL(url);
	};
	const filtered = entries?.filter((e) => e.qid.toLowerCase().includes(query.toLowerCase()));
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Operations",
			title: "History",
			description: "Every cached answer with its validation score, staleness, and pipeline versions.",
			actions: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
				variant: "outline",
				onClick: refresh,
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: "mr-1.5 h-4 w-4" }), " Refresh"]
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
				onClick: exportJson,
				disabled: !entries || entries.length === 0,
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Download, { className: "mr-1.5 h-4 w-4" }), " Export"]
			})] })
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "grid gap-3 px-6 py-4 sm:grid-cols-3",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatCard, {
					label: "Total entries",
					value: status?.total_entries ?? 0
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatCard, {
					label: "By subject",
					value: Object.entries(status?.by_subject ?? {}).map(([k, v]) => `${k.toUpperCase()} ${v}`).join(" · ") || "—",
					small: true
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatCard, {
					label: "Stale",
					value: Object.values(status?.stale_by_subject ?? {}).reduce((a, b) => a + b, 0),
					tone: "warn"
				})
			]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "flex flex-wrap items-center gap-2 px-6",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "relative flex-1 min-w-[240px]",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Search, { className: "pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
						value: query,
						onChange: (e) => setQuery(e.target.value),
						placeholder: "Search by qid…",
						className: "h-9 w-full rounded-md border border-border bg-background pl-8 pr-3 text-sm outline-none focus:border-primary"
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Segmented, {
					value: subject,
					onChange: setSubject,
					options: [{
						value: "all",
						label: "All"
					}, ...subjectOptions.filter((s) => s !== "all").map((s) => ({
						value: s,
						label: s.toUpperCase()
					}))]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
					onClick: () => setStaleOnly((v) => !v),
					className: cn("inline-flex h-9 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-sm text-muted-foreground transition-colors hover:text-foreground", staleOnly && "border-warning/50 bg-warning/10 text-warning"),
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Funnel, { className: "h-3.5 w-3.5" }), " Stale only"]
				})
			]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "p-6",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "overflow-hidden rounded-lg border border-border bg-surface",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("table", {
					className: "w-full text-sm",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("thead", {
						className: "bg-background/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", { children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "QID"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Subject"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Score"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Words"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Status"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Cached"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", { className: "px-4 py-3" })
						] })
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tbody", { children: [filtered?.map((e) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", {
						className: cn("border-t border-border transition-colors hover:bg-background/40", e.is_stale && "bg-warning/5"),
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 font-mono text-[12px]",
								children: e.qid
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
									tone: "primary",
									children: e.subject.toUpperCase()
								})
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums",
								children: e.validation_score != null ? Math.round(e.validation_score * 100) : "—"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums text-muted-foreground",
								children: e.target_word_count
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3",
								children: e.is_stale ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(StatusBadge, {
									tone: "warn",
									children: ["stale · ", e.stale_reasons[0]]
								}) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
									tone: "pass",
									children: "fresh"
								})
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 text-muted-foreground",
								children: formatTimestamp(e.cached_at)
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 text-right",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
									size: "sm",
									variant: "ghost",
									onClick: () => api.getCacheEntry(e.qid).then((entry) => {
										const text = entry.answer_text;
										const blob = new Blob([text], { type: "text/plain" });
										const url = URL.createObjectURL(blob);
										const a = document.createElement("a");
										a.href = url;
										a.download = `medrack-${e.qid}.txt`;
										a.click();
										URL.revokeObjectURL(url);
									}).catch((err) => alert(`Cache entry download failed: ${err.message}`)),
									children: "View"
								})
							})
						]
					}, e.qid)), !isLoading && filtered && filtered.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tr", { children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
						colSpan: 7,
						className: "px-4 py-10 text-center text-sm text-muted-foreground",
						children: "No cache entries match the current filters."
					}) })] })]
				})
			})
		})
	] });
}
function StatCard({ label, value, tone, small }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: cn("surface-card px-4 py-3", tone === "warn" && "border-warning/30 bg-warning/5"),
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "text-[10px] uppercase tracking-wider text-muted-foreground",
			children: label
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: cn("mt-1 font-display font-semibold tabular-nums", small ? "text-base" : "text-2xl"),
			children: value
		})]
	});
}
function Segmented({ value, onChange, options }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "inline-flex h-9 rounded-md border border-border bg-background p-0.5",
		children: options.map((o) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
			onClick: () => onChange(o.value),
			className: cn("rounded-[5px] px-3 text-sm font-medium text-muted-foreground transition-colors", value === o.value && "bg-primary/15 text-primary"),
			children: o.label
		}, o.value))
	});
}
//#endregion
export { HistoryPage as component };
