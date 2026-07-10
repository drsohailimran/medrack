import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, i as useQueryClient, n as useQuery, t as useMutation } from "../_libs/react+tanstack__react-query.mjs";
import { C as ChevronRight, b as Database, i as Trash2, l as RefreshCw, n as X, v as Eye, w as ChevronDown } from "../_libs/lucide-react.mjs";
import { n as api, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as AnswerViewer } from "./answer-viewer-BGqvZDob.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
import { n as formatTimestamp } from "./format-BX-FBxQr.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/answers-CeLWV1CC.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var safeStem = (s) => s.replace(/[^a-zA-Z0-9._-]/g, "");
var SINGLE_KEY = "__single__";
function CachedAnswersPage() {
	const qc = useQueryClient();
	const { data: entries } = useQuery({
		queryKey: ["cache-entries", "all"],
		queryFn: () => api.listCacheEntries({})
	});
	const { data: banks } = useQuery({
		queryKey: ["question-banks"],
		queryFn: () => api.listQuestionBanks()
	});
	const { data: status } = useQuery({
		queryKey: ["cache-status"],
		queryFn: () => api.getCacheStatus()
	});
	const [collapsed, setCollapsed] = (0, import_react.useState)({});
	const [viewQid, setViewQid] = (0, import_react.useState)(null);
	const refresh = () => {
		qc.invalidateQueries({ queryKey: ["cache-entries"] });
		qc.invalidateQueries({ queryKey: ["cache-status"] });
	};
	const deleteEntry = useMutation({
		mutationFn: ({ qid, module }) => api.deleteCacheEntry(qid, module),
		onSuccess: refresh
	});
	const deleteModule = useMutation({
		mutationFn: (module) => api.deleteCacheModule(module),
		onSuccess: refresh
	});
	const deleteMany = useMutation({
		mutationFn: async (items) => {
			for (const it of items) await api.deleteCacheEntry(it.qid, it.module);
		},
		onSuccess: refresh
	});
	const groups = (0, import_react.useMemo)(() => {
		const bankBySafe = /* @__PURE__ */ new Map();
		(banks ?? []).forEach((b) => bankBySafe.set(safeStem(b.name), b.name));
		const map = /* @__PURE__ */ new Map();
		for (const e of entries ?? []) {
			const mod = e.module || "";
			const bankName = bankBySafe.get(mod);
			if (bankName) {
				if (!map.has(mod)) map.set(mod, {
					key: mod,
					label: bankName,
					module: mod,
					isBank: true,
					entries: []
				});
				map.get(mod).entries.push(e);
			} else {
				if (!map.has(SINGLE_KEY)) map.set(SINGLE_KEY, {
					key: SINGLE_KEY,
					label: "Single answers (Workspace previews & tests)",
					module: "",
					isBank: false,
					entries: []
				});
				map.get(SINGLE_KEY).entries.push(e);
			}
		}
		const arr = Array.from(map.values());
		arr.sort((a, b) => a.isBank === b.isBank ? a.label.localeCompare(b.label) : a.isBank ? -1 : 1);
		return arr;
	}, [entries, banks]);
	const total = entries?.length ?? 0;
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Operations",
			title: "Cached Answers",
			description: "Every answer MedRack has generated is cached here, grouped by question bank. Delete any you don't like — they'll be regenerated fresh next time you solve.",
			actions: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
				variant: "outline",
				onClick: refresh,
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: "mr-1.5 h-4 w-4" }), " Refresh"]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "grid gap-3 px-6 py-4 sm:grid-cols-3",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatCard, {
					label: "Total cached answers",
					value: total
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatCard, {
					label: "Question banks",
					value: groups.filter((g) => g.isBank).length
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatCard, {
					label: "By subject",
					value: Object.entries(status?.by_subject ?? {}).map(([s, n]) => `${s.toUpperCase()}:${n}`).join("  ") || "—"
				})
			]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "space-y-4 px-6 pb-10",
			children: [groups.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "surface-card p-10 text-center text-sm text-muted-foreground",
				children: "No cached answers yet. Generate or solve some answers and they'll appear here."
			}), groups.map((g) => {
				const isCollapsed = collapsed[g.key];
				return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "surface-card overflow-hidden",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-center justify-between gap-3 border-b border-border bg-surface-2 px-4 py-3",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
							className: "flex min-w-0 items-center gap-2 text-left",
							onClick: () => setCollapsed((c) => ({
								...c,
								[g.key]: !c[g.key]
							})),
							children: [
								isCollapsed ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ChevronRight, { className: "h-4 w-4 shrink-0 text-muted-foreground" }) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ChevronDown, { className: "h-4 w-4 shrink-0 text-muted-foreground" }),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Database, { className: "h-4 w-4 shrink-0 text-primary" }),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "truncate font-display text-sm font-semibold",
									children: g.label
								}),
								g.isBank && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
									tone: "primary",
									children: "bank"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
									className: "text-xs text-muted-foreground",
									children: [
										g.entries.length,
										" answer",
										g.entries.length === 1 ? "" : "s"
									]
								})
							]
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
							variant: "ghost",
							size: "sm",
							className: "shrink-0 text-muted-foreground hover:text-destructive",
							onClick: () => {
								if (!confirm(`Delete all ${g.entries.length} cached answers in "${g.label}"?`)) return;
								if (g.isBank) deleteModule.mutate(g.module);
								else deleteMany.mutate(g.entries.map((e) => ({
									qid: e.qid,
									module: e.module
								})));
							},
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Trash2, { className: "mr-1.5 h-3.5 w-3.5" }), " Delete all"]
						})]
					}), !isCollapsed && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("ul", {
						className: "divide-y divide-border",
						children: g.entries.map((e) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("li", {
							className: "flex items-center gap-3 px-4 py-2.5",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
									className: "min-w-0 flex-1",
									children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
										className: "truncate text-sm",
										children: e.question_text || /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
											className: "font-mono text-xs",
											children: e.qid
										})
									}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
										className: "mt-0.5 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground",
										children: [
											/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
												className: "font-mono",
												children: e.qid
											}),
											/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["· ", e.subject?.toUpperCase()] }),
											e.target_word_count ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: [
												"· ~",
												e.target_word_count,
												" w"
											] }) : null,
											e.cached_at ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["· ", formatTimestamp(e.cached_at)] }) : null,
											e.is_stale ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
												tone: "warn",
												children: "stale"
											}) : null
										]
									})]
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
									variant: "ghost",
									size: "sm",
									title: "View answer",
									onClick: () => setViewQid(e.qid),
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eye, { className: "h-3.5 w-3.5" })
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
									variant: "ghost",
									size: "sm",
									title: "Delete this cached answer",
									className: "text-muted-foreground hover:text-destructive",
									onClick: () => {
										if (confirm(`Delete the cached answer for "${e.qid}"?`)) deleteEntry.mutate({
											qid: e.qid,
											module: e.module
										});
									},
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Trash2, { className: "h-3.5 w-3.5" })
								})
							]
						}, e.qid))
					})]
				}, g.key);
			})]
		}),
		viewQid && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(AnswerModal, {
			qid: viewQid,
			onClose: () => setViewQid(null)
		})
	] });
}
function AnswerModal({ qid, onClose }) {
	const { data, isLoading } = useQuery({
		queryKey: ["cache-entry", qid],
		queryFn: () => api.getCacheEntry(qid)
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4",
		onClick: onClose,
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "surface-card flex max-h-[88vh] w-full max-w-3xl flex-col p-0",
			onClick: (ev) => ev.stopPropagation(),
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex items-start justify-between border-b border-border px-6 py-3",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "min-w-0",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "truncate font-display text-sm font-semibold",
						children: qid
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "truncate text-xs text-muted-foreground",
						children: data?.question_text || "Cached answer"
					})]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
					onClick: onClose,
					className: "rounded p-1 text-muted-foreground hover:bg-surface-2 hover:text-foreground",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(X, { className: "h-4 w-4" })
				})]
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "min-h-0 flex-1 overflow-auto",
				children: [isLoading && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "p-6 text-sm text-muted-foreground",
					children: "Loading…"
				}), data?.answer_text ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(AnswerViewer, { answer: data.answer_text }) : !isLoading && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "p-6 text-sm text-muted-foreground",
					children: "No answer text."
				})]
			})]
		})
	});
}
function StatCard({ label, value }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "surface-card p-4",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "text-[11px] uppercase tracking-wider text-muted-foreground",
			children: label
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "mt-1 font-display text-xl font-semibold tabular-nums",
			children: value
		})]
	});
}
//#endregion
export { CachedAnswersPage as component };
