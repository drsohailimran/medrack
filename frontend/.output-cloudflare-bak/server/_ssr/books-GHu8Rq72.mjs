import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, i as useQueryClient, n as useQuery, t as useMutation } from "../_libs/react+tanstack__react-query.mjs";
import { T as BookOpen, i as Trash2, j as CloudUpload, l as RefreshCw, u as Plus } from "../_libs/lucide-react.mjs";
import { n as api, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
import { t as formatDate } from "./format-BX-FBxQr.mjs";
import { n as useJob, t as ProgressBar } from "./use-job-DrhZwuCz.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/books-GHu8Rq72.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var KNOWN_SUBJECTS = [
	{
		value: "psm",
		label: "PSM"
	},
	{
		value: "fmt",
		label: "FMT"
	},
	{
		value: "medicine",
		label: "Medicine"
	},
	{
		value: "surgery",
		label: "Surgery"
	},
	{
		value: "obgyn",
		label: "OBGYN"
	},
	{
		value: "pediatrics",
		label: "Pediatrics"
	},
	{
		value: "ortho",
		label: "Ortho"
	},
	{
		value: "ent",
		label: "ENT"
	},
	{
		value: "ophthalmology",
		label: "Ophth"
	},
	{
		value: "anesthesia",
		label: "Anesth"
	}
];
function BooksPage() {
	const { data: books, isLoading, refetch } = useQuery({
		queryKey: ["books"],
		queryFn: () => api.listBooks()
	});
	const qc = useQueryClient();
	const [showImportDialog, setShowImportDialog] = (0, import_react.useState)(false);
	const [importSubject, setImportSubject] = (0, import_react.useState)("psm");
	const [importTitle, setImportTitle] = (0, import_react.useState)("");
	const [importFile, setImportFile] = (0, import_react.useState)(null);
	const [replaceExisting, setReplaceExisting] = (0, import_react.useState)(false);
	const [importError, setImportError] = (0, import_react.useState)(null);
	const [actionMessage, setActionMessage] = (0, import_react.useState)(null);
	const ingest = useJob("medrack:ingestJob");
	const importMutation = useMutation({
		mutationFn: () => {
			if (!importFile) throw new Error("Choose a PDF file to upload.");
			return api.uploadBook({
				file: importFile,
				subject: importSubject,
				title: importTitle.trim() || importFile.name.replace(/\.pdf$/i, ""),
				replace: replaceExisting
			});
		},
		onSuccess: (handle) => {
			setImportError(null);
			ingest.start(handle.job_id);
		},
		onError: (err) => setImportError(err.message)
	});
	(0, import_react.useEffect)(() => {
		const st = ingest.job?.status;
		if (st === "done") {
			const r = ingest.job?.result ?? {};
			setActionMessage(`Ingested "${importTitle || importFile?.name || "book"}" — ${r.chunks ?? 0} chunks from ${r.pages ?? 0} pages indexed.`);
			qc.invalidateQueries({ queryKey: ["books"] });
			setShowImportDialog(false);
			setImportFile(null);
			setImportTitle("");
			ingest.reset();
		} else if (st === "error") setImportError(ingest.job?.error ?? "Ingestion failed.");
	}, [ingest.job?.status]);
	const ingesting = ingest.job != null && ingest.job.status !== "done" && ingest.job.status !== "error";
	const busy = importMutation.isPending || ingesting;
	const deleteMutation = useMutation({
		mutationFn: (book_id) => api.removeBook(book_id),
		onSuccess: (data) => {
			if (data.ok === false) setActionMessage(`Delete failed: ${data.error ?? "book not found"}`);
			else setActionMessage(`Deleted book — its indexed chunks were removed from the knowledge base. Upload a fresh copy anytime.`);
			qc.invalidateQueries({ queryKey: ["books"] });
		},
		onError: (err) => setActionMessage(`Delete failed: ${err.message}`)
	});
	const subjectOptions = Array.from(/* @__PURE__ */ new Set([...KNOWN_SUBJECTS.map((s) => s.value), ...books?.map((b) => b.subject).filter(Boolean) ?? []]));
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Library",
			title: "Books",
			description: "Textbook PDFs indexed into the retrieval store. Every claim in a generated answer is grounded in chunks from these sources.",
			actions: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex items-center gap-2",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					variant: "outline",
					size: "sm",
					onClick: () => refetch(),
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(RefreshCw, { className: "mr-1.5 h-4 w-4" }), " Refresh"]
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					onClick: () => setShowImportDialog(true),
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Plus, { className: "mr-1.5 h-4 w-4" }), " Import book"]
				})]
			})
		}),
		actionMessage && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "mx-6 mt-4 flex items-center justify-between rounded-md border border-info/30 bg-info/10 px-3 py-2 text-[12px] text-info-foreground",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: actionMessage }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
				onClick: () => setActionMessage(null),
				className: "text-info-foreground/70 hover:text-info-foreground",
				children: "dismiss"
			})]
		}),
		showImportDialog && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card max-h-[90vh] w-full max-w-md overflow-y-auto p-6",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "text-lg font-semibold",
						children: "Import Book"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: "Upload a PDF from this device. It is ingested into the knowledge base (extract → chunk → embed → index into ChromaDB) with live progress."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-4 space-y-3",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
								className: "text-sm font-medium",
								children: "PDF file"
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
								className: "mt-1 flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-border bg-background px-3 py-2 text-sm hover:border-primary/50",
								children: [
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CloudUpload, { className: "h-4 w-4 shrink-0 text-muted-foreground" }),
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
										className: "truncate",
										children: importFile ? importFile.name : "Choose a PDF…"
									}),
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
										type: "file",
										accept: "application/pdf",
										className: "hidden",
										disabled: busy,
										onChange: (e) => {
											const f = e.target.files?.[0] ?? null;
											setImportFile(f);
											if (f && !importTitle) setImportTitle(f.name.replace(/\.pdf$/i, ""));
										}
									})
								]
							})] }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
								className: "text-sm font-medium",
								children: "Subject"
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("select", {
								value: importSubject,
								onChange: (e) => setImportSubject(e.target.value),
								className: "mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm",
								children: subjectOptions.map((s) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
									value: s,
									children: s.toUpperCase()
								}, s))
							})] }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
								className: "text-sm font-medium",
								children: "Book Title (optional)"
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
								type: "text",
								placeholder: "Auto-generated from filename if empty",
								value: importTitle,
								onChange: (e) => setImportTitle(e.target.value),
								className: "mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
							})] }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
								className: "flex items-center gap-2 text-xs text-muted-foreground",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
									type: "checkbox",
									checked: replaceExisting,
									onChange: (e) => setReplaceExisting(e.target.checked),
									disabled: busy
								}), "Replace if this book is already in the knowledge base"]
							})
						]
					}),
					ingesting && ingest.job && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-4",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ProgressBar, {
							percent: ingest.job.percent,
							label: ingest.job.message || "Ingesting…"
						})
					}),
					importError && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive",
						children: importError
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-6 flex justify-end gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							variant: "outline",
							onClick: () => {
								setShowImportDialog(false);
								ingest.reset();
								setImportError(null);
							},
							disabled: importMutation.isPending,
							children: ingesting ? "Close" : "Cancel"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							onClick: () => importMutation.mutate(),
							disabled: busy || !importFile,
							children: busy ? "Ingesting…" : "Upload & ingest"
						})]
					})
				]
			})
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
								children: "Title"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Subject"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 font-medium",
								children: "Status"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Chunks"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", {
								className: "px-4 py-3 text-right font-medium",
								children: "Indexed"
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("th", { className: "px-4 py-3" })
						] })
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tbody", { children: [
						isLoading && [...Array(3)].map((_, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tr", {
							className: "border-t border-border",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
								colSpan: 6,
								className: "px-4 py-4",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: "h-5 w-full animate-pulse rounded bg-muted/40" })
							})
						}, i)),
						books?.map((b) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("tr", {
							className: "border-t border-border transition-colors hover:bg-background/40",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-3",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
										className: "flex items-center gap-3",
										children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
											className: "grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20",
											children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(BookOpen, { className: "h-4 w-4" })
										}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
											className: "min-w-0",
											children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
												className: "truncate font-medium text-foreground",
												children: b.title
											}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
												className: "truncate font-mono text-[11px] text-muted-foreground",
												children: b.book_id
											})]
										})]
									})
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-3",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
										tone: "primary",
										children: b.subject.toUpperCase()
									})
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-3",
									children: b.indexed ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
										tone: "pass",
										children: "indexed"
									}) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
										tone: "warn",
										children: "indexing"
									})
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-3 text-right font-mono tabular-nums text-muted-foreground",
									children: b.chunk_count.toLocaleString()
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-3 text-right text-muted-foreground",
									children: formatDate(b.indexed_at)
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("td", {
									className: "px-4 py-3 text-right",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
										variant: "ghost",
										size: "sm",
										title: "Delete book",
										className: "text-muted-foreground hover:text-destructive",
										onClick: () => {
											if (confirm(`Delete "${b.title}"? This removes its indexed chunks from the knowledge base. You can upload a fresh copy afterwards.`)) deleteMutation.mutate(b.book_id);
										},
										disabled: deleteMutation.isPending && deleteMutation.variables === b.book_id,
										children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Trash2, { className: "mr-1.5 h-3.5 w-3.5" }), " Delete"]
									})
								})
							]
						}, b.book_id)),
						books && books.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("tr", {
							className: "border-t border-border",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("td", {
								colSpan: 6,
								className: "px-4 py-12 text-center text-sm text-muted-foreground",
								children: [
									"No books yet. Click",
									" ",
									/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
										className: "font-medium text-foreground",
										children: "Import book"
									}),
									" to add your first textbook."
								]
							})
						})
					] })]
				})
			})
		})
	] });
}
//#endregion
export { BooksPage as component };
