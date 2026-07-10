import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { h as FolderKanban, u as Plus } from "../_libs/lucide-react.mjs";
import { n as api, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/projects-COhdAmtf.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var SAMPLE_PROJECTS = [{
	id: "psm-3rd-year",
	name: "PSM · 3rd Year",
	subject: "psm",
	description: "Community Medicine exam prep for the third-year MBBS block.",
	question_count: 18,
	created_at: "2026-06-15T00:00:00Z",
	updated_at: "2026-06-30T00:00:00Z"
}, {
	id: "fmt-finals",
	name: "FMT · Finals",
	subject: "fmt",
	description: "Forensic Medicine & Toxicology revision block for the final-year exam.",
	question_count: 12,
	created_at: "2026-06-20T00:00:00Z",
	updated_at: "2026-06-29T00:00:00Z"
}];
function ProjectsPage() {
	const { data: books } = useQuery({
		queryKey: ["books"],
		queryFn: () => api.listBooks()
	});
	const [openNew, setOpenNew] = (0, import_react.useState)(false);
	const [name, setName] = (0, import_react.useState)("");
	const [subject, setSubject] = (0, import_react.useState)("psm");
	const [description, setDescription] = (0, import_react.useState)("");
	const [projects, setProjects] = (0, import_react.useState)(() => SAMPLE_PROJECTS.map((p) => ({ ...p })));
	const create = () => {
		if (!name.trim()) return;
		const now = (/* @__PURE__ */ new Date()).toISOString();
		setProjects((cur) => [...cur, {
			id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
			name,
			subject,
			description: description || "Local project grouping.",
			question_count: 0,
			created_at: now,
			updated_at: now
		}]);
		setName("");
		setDescription("");
		setOpenNew(false);
	};
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Workspace",
			title: "Projects",
			description: "Local groupings of related questions. The backend stores by subject + module, not by named project — projects are a frontend-only convenience.",
			actions: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
				onClick: () => setOpenNew(true),
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Plus, { className: "mr-1.5 h-4 w-4" }), " New project"]
			})
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "px-6 py-3 text-[11px] text-muted-foreground",
			children: [
				"Available subjects from imported books:",
				" ",
				Array.from(new Set(books?.map((b) => b.subject) ?? [])).join(", ") || "—"
			]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3",
			children: projects.map((p) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card flex flex-col gap-3 p-5 transition-colors hover:bg-surface-2",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-start justify-between",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(FolderKanban, { className: "h-5 w-5" })
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
							tone: "primary",
							children: p.subject.toUpperCase()
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "font-display text-base font-semibold tracking-tight",
						children: p.name
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: p.description
					})] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-auto flex items-center justify-between border-t border-border pt-3 text-[11px] text-muted-foreground",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-foreground",
							children: p.question_count
						}), " questions"] }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["Updated ", new Date(p.updated_at).toLocaleDateString()] })]
					})
				]
			}, p.id))
		}),
		openNew && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "fixed inset-0 z-50 flex items-center justify-center bg-black/50",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card w-full max-w-md p-6",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "text-lg font-semibold",
						children: "New project"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: "Projects are saved locally in this browser. They are not synced to the backend. Use subjects to organize work on the server."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-4 space-y-3 text-sm",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
								className: "block",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
									children: "Name"
								}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
									value: name,
									onChange: (e) => setName(e.target.value),
									placeholder: "e.g. Surgery · Block 4",
									className: "w-full rounded-md border border-border bg-background px-3 py-2"
								})]
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
								className: "block",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
									children: "Subject"
								}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
									value: subject,
									onChange: (e) => setSubject(e.target.value),
									className: "w-full rounded-md border border-border bg-background px-3 py-2"
								})]
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
								className: "block",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
									children: "Description (optional)"
								}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("textarea", {
									value: description,
									onChange: (e) => setDescription(e.target.value),
									rows: 3,
									className: "w-full rounded-md border border-border bg-background px-3 py-2"
								})]
							})
						]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-6 flex justify-end gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							variant: "outline",
							onClick: () => setOpenNew(false),
							children: "Cancel"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							onClick: create,
							disabled: !name.trim(),
							children: "Create"
						})]
					})
				]
			})
		})
	] });
}
//#endregion
export { ProjectsPage as component };
