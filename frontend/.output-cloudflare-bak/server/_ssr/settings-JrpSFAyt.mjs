import { a as require_jsx_runtime, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { n as api, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/settings-JrpSFAyt.js
var import_jsx_runtime = require_jsx_runtime();
function SettingsPage() {
	const { data: v } = useQuery({
		queryKey: ["version"],
		queryFn: () => api.getVersion()
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
		eyebrow: "System",
		title: "Settings",
		description: "Backend version, pipeline versions, and frontend preferences."
	}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "grid gap-6 p-6 lg:grid-cols-2",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "surface-card p-5",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "font-display text-base font-semibold tracking-tight",
					children: "Backend"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "mt-4 space-y-3 text-sm",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Row, {
							label: "Package version",
							value: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "font-mono",
								children: v?.package_version ?? "—"
							})
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Row, {
							label: "Schema version",
							value: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "font-mono",
								children: v?.schema_version ?? "—"
							})
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Row, {
							label: "Benchmark baseline",
							value: v?.benchmark_baseline_tag ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
								tone: "primary",
								children: v.benchmark_baseline_tag
							}) : "—"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Row, {
							label: "API base",
							value: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "font-mono text-muted-foreground",
								children: "http://localhost:8000/api/v1"
							})
						})
					]
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "surface-card p-5",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "font-display text-base font-semibold tracking-tight",
					children: "Pipeline versions"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("table", {
					className: "mt-4 w-full text-sm",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tbody", { children: v && Object.entries(v.pipeline_versions).map(([k, val]) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", {
						className: "border-t border-border first:border-0",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
							className: "py-2 capitalize text-muted-foreground",
							children: k
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
							className: "py-2 text-right font-mono tabular-nums",
							children: val
						})]
					}, k)) })
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
				className: "surface-card p-5 lg:col-span-2",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "font-display text-base font-semibold tracking-tight",
						children: "Frontend preferences"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-sm text-muted-foreground",
						children: "Purely client-side — never sent to the backend."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Pref, {
								label: "Theme",
								value: "Dark"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Pref, {
								label: "Default subject",
								value: "PSM"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Pref, {
								label: "Default marks",
								value: "10"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Pref, {
								label: "Polling interval",
								value: "5s"
							})
						]
					})
				]
			})
		]
	})] });
}
function Row({ label, value }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex items-center justify-between border-t border-border pt-2 first:border-0 first:pt-0",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "text-muted-foreground",
			children: label
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: value })]
	});
}
function Pref({ label, value }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "rounded-md border border-border bg-background px-4 py-3",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "text-[10px] uppercase tracking-wider text-muted-foreground",
			children: label
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "mt-1 font-display text-base font-semibold",
			children: value
		})]
	});
}
//#endregion
export { SettingsPage as component };
