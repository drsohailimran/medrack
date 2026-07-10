import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { D as ArrowDownRight, E as ArrowUpRight, P as ChartLine, m as GitCompare, t as Zap } from "../_libs/lucide-react.mjs";
import { n as api, r as cn, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
import { n as formatTimestamp } from "./format-BX-FBxQr.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/benchmarks-BK0VaThl.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function BenchmarksPage() {
	const { data: runs } = useQuery({
		queryKey: ["benchmarks"],
		queryFn: () => api.listBenchmarkRuns()
	});
	const [selected, setSelected] = (0, import_react.useState)([]);
	const toggle = (id) => setSelected((sel) => sel.includes(id) ? sel.filter((x) => x !== id) : sel.length < 2 ? [...sel, id] : [sel[1], id]);
	const { data: compare } = useQuery({
		queryKey: ["benchmark-compare", selected],
		queryFn: () => api.compareBenchmarks(selected[0], selected[1]),
		enabled: selected.length === 2
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Operations",
			title: "Benchmarks",
			description: "Past pipeline runs across the regression dataset. Compare two runs to see token, latency, and cache deltas.",
			actions: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
				disabled: selected.length !== 2,
				onClick: () => {
					if (selected.length === 2) api.compareBenchmarks(selected[0], selected[1]).catch(() => {});
				},
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)(GitCompare, { className: "mr-1.5 h-4 w-4" }),
					" Compare ",
					selected.length,
					"/2"
				]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "grid gap-4 px-6 py-4 sm:grid-cols-4",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
					label: "Latest avg latency",
					value: runs?.[0] ? `${runs[0].avg_total_latency_seconds.toFixed(2)}s` : "—",
					icon: ChartLine
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
					label: "Latest cache hit",
					value: runs?.[0] ? `${Math.round(runs[0].cache_hit_rate * 100)}%` : "—",
					icon: Zap
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
					label: "Latest tokens",
					value: runs?.[0] ? runs[0].total_tokens.toLocaleString() : "—"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Kpi, {
					label: "Runs stored",
					value: runs?.length ?? 0
				})
			]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "p-6",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "overflow-hidden rounded-lg border border-border bg-surface",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("table", {
					className: "w-full text-sm",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("thead", {
						className: "bg-background/50 text-left text-[11px] uppercase tracking-wider text-muted-foreground",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", { children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", { className: "w-10 px-3 py-3" }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Run"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Mode"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Questions"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Success"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Cache hit"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Tokens"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Avg latency"
							})
						] })
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tbody", { children: runs?.map((r) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", {
						className: cn("border-t border-border", selected.includes(r.run_id) && "bg-primary/5"),
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-3 py-3",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
									type: "checkbox",
									checked: selected.includes(r.run_id),
									onChange: () => toggle(r.run_id),
									className: "h-3.5 w-3.5 accent-primary"
								})
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
								className: "px-4 py-3",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
									className: "font-mono text-[12px] text-foreground",
									children: r.run_id
								}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
									className: "text-[11px] text-muted-foreground",
									children: formatTimestamp(r.timestamp)
								})]
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
									tone: r.llm_mode === "real" ? "primary" : "info",
									children: r.llm_mode
								})
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums",
								children: r.n_questions
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums",
								children: [
									Math.round(r.n_success / Math.max(1, r.n_success + r.n_failure) * 100),
									"%",
									/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
										className: "ml-1 text-[10px] text-muted-foreground",
										children: [
											"(",
											r.n_success,
											"/",
											r.n_success + r.n_failure,
											")"
										]
									})
								]
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums text-success",
								children: [Math.round(r.cache_hit_rate * 100), "%"]
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums text-muted-foreground",
								children: r.total_tokens.toLocaleString()
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
								className: "px-4 py-3 text-right font-mono tabular-nums",
								children: [r.avg_total_latency_seconds.toFixed(2), "s"]
							})
						]
					}, r.run_id)) })]
				})
			}), compare && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card mt-6 p-5",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "mb-3 flex items-center justify-between",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground",
						children: "Comparison"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "font-display text-base font-semibold",
						children: [
							compare.run_a,
							" ",
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "text-muted-foreground",
								children: "→"
							}),
							" ",
							compare.run_b
						]
					})] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
						tone: "primary",
						children: "delta"
					})]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "grid gap-3 sm:grid-cols-3 lg:grid-cols-6",
					children: Object.entries(compare.delta).map(([k, v]) => {
						const positive = v > 0;
						const negative = v < 0;
						const good = k.includes("latency") || k.includes("tokens") || k === "n_failure" ? negative : positive;
						return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "rounded-md border border-border bg-background px-3 py-2",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
								className: "text-[10px] uppercase tracking-wider text-muted-foreground",
								children: k
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: cn("mt-0.5 flex items-center gap-1 font-mono text-sm font-semibold tabular-nums", v === 0 && "text-muted-foreground", v !== 0 && good && "text-success", v !== 0 && !good && "text-destructive"),
								children: [
									positive && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowUpRight, { className: "h-3.5 w-3.5" }),
									negative && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ArrowDownRight, { className: "h-3.5 w-3.5" }),
									typeof v === "number" ? Number.isInteger(v) ? v : v.toFixed(2) : v
								]
							})]
						}, k);
					})
				})]
			})]
		})
	] });
}
function Kpi({ label, value, icon: Icon }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "surface-card flex items-center gap-3 px-4 py-3",
		children: [Icon && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "grid h-9 w-9 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Icon, { className: "h-4 w-4" })
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "text-[10px] uppercase tracking-wider text-muted-foreground",
			children: label
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "font-display text-xl font-semibold tabular-nums",
			children: value
		})] })]
	});
}
//#endregion
export { BenchmarksPage as component };
