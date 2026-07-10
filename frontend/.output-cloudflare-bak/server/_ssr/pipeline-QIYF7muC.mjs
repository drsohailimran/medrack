import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { C as ChevronRight, S as Clock, d as Play, w as ChevronDown } from "../_libs/lucide-react.mjs";
import { n as api, r as cn, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/pipeline-QIYF7muC.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function isObj(v) {
	return typeof v === "object" && v !== null && !Array.isArray(v);
}
function JsonTree({ value, depth = 0 }) {
	if (value === null) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
		className: "text-muted-foreground",
		children: "null"
	});
	if (typeof value === "boolean") return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
		className: "text-chart-2",
		children: String(value)
	});
	if (typeof value === "number") return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
		className: "text-chart-3",
		children: value
	});
	if (typeof value === "string") return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
		className: "text-success",
		children: [
			"\"",
			value,
			"\""
		]
	});
	if (Array.isArray(value)) {
		if (value.length === 0) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "text-muted-foreground",
			children: "[]"
		});
		return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Collapsible, {
			label: `Array(${value.length})`,
			depth,
			children: value.map((v, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex gap-2",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "select-none text-muted-foreground",
					children: i
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(JsonTree, {
					value: v,
					depth: depth + 1
				})]
			}, i))
		});
	}
	if (isObj(value)) {
		const keys = Object.keys(value);
		if (keys.length === 0) return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "text-muted-foreground",
			children: `{}`
		});
		return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Collapsible, {
			label: `Object · ${keys.length} keys`,
			depth,
			children: keys.map((k) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex gap-2",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
					className: "select-none text-chart-2",
					children: [k, ":"]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(JsonTree, {
					value: value[k],
					depth: depth + 1
				})]
			}, k))
		});
	}
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: String(value) });
}
function Collapsible({ label, children, depth }) {
	const [open, setOpen] = (0, import_react.useState)(depth < 1);
	const id = (0, import_react.useId)();
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "font-mono text-[12px]",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
			type: "button",
			"aria-expanded": open,
			"aria-controls": id,
			onClick: () => setOpen((v) => !v),
			className: "inline-flex items-center gap-1 rounded text-muted-foreground transition-colors hover:text-foreground",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(ChevronRight, { className: cn("h-3 w-3 transition-transform", open && "rotate-90") }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
				className: "text-[11px]",
				children: label
			})]
		}), open && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			id,
			className: "ml-3 border-l border-border/70 pl-3",
			children
		})]
	});
}
var STAGE_META = {
	planner: {
		label: "Planner",
		hint: "Deterministic blueprint of sections & word allocations"
	},
	blueprint: {
		label: "Blueprint",
		hint: "Retrieval-aware enrichment of the planner output"
	},
	retrieval: {
		label: "Retrieval",
		hint: "Adaptive vector search over book chunks"
	},
	reranker: {
		label: "Reranker",
		hint: "Re-orders evidence by semantic relevance"
	},
	writer: {
		label: "Writer",
		hint: "Synthesizes prose from blueprint + evidence"
	},
	validator: {
		label: "Validator",
		hint: "Runs 9 quality rules against the answer"
	}
};
function PipelinePanel({ trace, loading, onInspect }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex h-full flex-col",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "flex items-center justify-between border-b border-border px-4 py-3",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground",
				children: "Pipeline"
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "text-sm font-semibold",
				children: "Trace"
			})] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex items-center gap-2",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "text-right text-[11px] text-muted-foreground",
					children: trace ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
						"Total ",
						trace.total_latency_seconds.toFixed(3),
						"s"
					] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "font-mono",
						children: trace.qid
					})] }) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { children: "—" })
				}), onInspect && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					size: "sm",
					variant: "outline",
					onClick: onInspect,
					disabled: loading,
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Play, { className: "mr-1.5 h-3.5 w-3.5" }), "Inspect"]
				})]
			})]
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "min-h-0 flex-1 overflow-y-auto",
			children: [
				!trace && !loading && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "px-4 py-6 text-xs text-muted-foreground",
					children: "Generate or inspect a question to populate pipeline stages."
				}),
				loading && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "space-y-2 p-4",
					children: [...Array(6)].map((_, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "h-9 animate-pulse rounded-md bg-muted/40" }, i))
				}),
				trace?.stages.map((stage, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Stage, {
					stage,
					index: i + 1,
					defaultOpen: i < 2
				}, stage.stage))
			]
		})]
	});
}
function Stage({ stage, index, defaultOpen }) {
	const [open, setOpen] = (0, import_react.useState)(!!defaultOpen);
	const meta = STAGE_META[stage.stage] ?? {
		label: stage.stage,
		hint: ""
	};
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "border-b border-border last:border-0",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
			onClick: () => setOpen((v) => !v),
			className: cn("flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-accent/40", open && "bg-accent/30"),
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "grid h-6 w-6 shrink-0 place-items-center rounded-md bg-primary/10 font-mono text-[10px] text-primary ring-1 ring-primary/30",
					children: index
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "min-w-0 flex-1",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-center gap-2 text-[13px] font-medium",
						children: [meta.label, /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "rounded-full bg-success/10 px-1.5 py-0.5 text-[9px] font-medium text-success ring-1 ring-inset ring-success/20",
							children: "ok"
						})]
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "truncate text-[11px] text-muted-foreground",
						children: meta.hint
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
					className: "flex items-center gap-1 font-mono text-[10px] text-muted-foreground",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Clock, { className: "h-3 w-3" }),
						stage.latency_seconds.toFixed(3),
						"s"
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(ChevronDown, { className: cn("h-4 w-4 text-muted-foreground transition-transform", open && "rotate-180") })
			]
		}), open && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "bg-background/60 px-5 py-3",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(JsonTree, { value: stage.output })
		})]
	});
}
function Field({ label, children }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
		className: "block",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "mb-1.5 block text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground",
			children: label
		}), children]
	});
}
var Textarea = import_react.forwardRef(({ className, ...props }, ref) => {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("textarea", {
		className: cn("flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-base shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 md:text-sm", className),
		ref,
		...props
	});
});
Textarea.displayName = "Textarea";
function PipelinePage() {
	const [qid, setQid] = (0, import_react.useState)("q001");
	const [question, setQuestion] = (0, import_react.useState)("Discuss the management of diabetes mellitus.");
	const [subject, setSubject] = (0, import_react.useState)("psm");
	const [marks, setMarks] = (0, import_react.useState)(10);
	const [submitted, setSubmitted] = (0, import_react.useState)(true);
	const { data: trace, isFetching, refetch } = useQuery({
		queryKey: [
			"inspect",
			qid,
			question,
			subject,
			marks,
			submitted
		],
		queryFn: () => api.inspectPipeline({
			qid,
			question_text: question,
			subject,
			marks
		}),
		enabled: submitted
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
		eyebrow: "Operations",
		title: "Pipeline Inspector",
		description: "Read-only trace of all six pipeline stages for a given question. Useful when verifying blueprints and retrieval configuration."
	}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "grid h-[calc(100%-7.5rem)] grid-cols-1 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("aside", {
			className: "space-y-4 border-r border-border p-6",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
					label: "QID",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
						value: qid,
						onChange: (e) => setQid(e.target.value),
						className: "h-9 w-full rounded-md border border-border bg-background px-3 font-mono text-sm outline-none focus:border-primary"
					})
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
					label: "Question text",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Textarea, {
						value: question,
						onChange: (e) => setQuestion(e.target.value),
						className: "min-h-[140px] bg-background"
					})
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "grid grid-cols-2 gap-3",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						label: "Subject",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Seg, {
							value: subject,
							onChange: (v) => setSubject(v),
							options: [{
								value: "psm",
								label: "PSM"
							}, {
								value: "fmt",
								label: "FMT"
							}]
						})
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
						label: "Marks",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Seg, {
							value: String(marks),
							onChange: (v) => setMarks(Number(v)),
							options: [
								{
									value: "5",
									label: "5"
								},
								{
									value: "10",
									label: "10"
								},
								{
									value: "15",
									label: "15"
								}
							]
						})
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					onClick: () => {
						setSubmitted(true);
						refetch();
					},
					className: "w-full",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Play, { className: "mr-2 h-4 w-4" }), " Inspect pipeline"]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "text-[11px] text-muted-foreground",
					children: "This call does not trigger generation. It returns each stage's configuration and reported latency."
				})
			]
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "min-h-0 overflow-hidden",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(PipelinePanel, {
				trace,
				loading: isFetching
			})
		})]
	})] });
}
function Seg({ value, onChange, options }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "grid grid-flow-col rounded-md border border-border bg-background p-0.5",
		children: options.map((o) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
			onClick: () => onChange(o.value),
			className: cn("rounded px-2 py-1 text-[12px] font-medium text-muted-foreground transition-colors", value === o.value && "bg-primary/15 text-primary ring-1 ring-inset ring-primary/30"),
			children: o.label
		}, o.value))
	});
}
//#endregion
export { PipelinePage as component };
