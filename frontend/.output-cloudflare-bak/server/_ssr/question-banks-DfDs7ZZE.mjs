import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, i as useQueryClient, n as useQuery, t as useMutation } from "../_libs/react+tanstack__react-query.mjs";
import { g as FileUp, i as Trash2, n as X, p as Library, r as Upload, v as Eye } from "../_libs/lucide-react.mjs";
import { n as api, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as PageHeader } from "./page-header-D6T00jhG.mjs";
import { t as StatusBadge } from "./status-badge-C4TmVFa6.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
import { n as formatTimestamp } from "./format-BX-FBxQr.mjs";
import { n as useJob, t as ProgressBar } from "./use-job-DrhZwuCz.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/question-banks-DfDs7ZZE.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
var KNOWN_SUBJECTS = [
	"psm",
	"fmt",
	"medicine",
	"surgery",
	"obgyn",
	"pediatrics",
	"ortho",
	"ent",
	"ophthalmology",
	"anesthesia"
];
function QuestionBanksPage() {
	const { data } = useQuery({
		queryKey: ["question-banks"],
		queryFn: () => api.listQuestionBanks()
	});
	const [showUpload, setShowUpload] = (0, import_react.useState)(false);
	const [bankName, setBankName] = (0, import_react.useState)("regression-v1");
	const [bankSubject, setBankSubject] = (0, import_react.useState)("psm");
	const [bankVersion, setBankVersion] = (0, import_react.useState)("v1");
	const [pickedFile, setPickedFile] = (0, import_react.useState)(null);
	const [result, setResult] = (0, import_react.useState)(null);
	const fileRef = (0, import_react.useRef)(null);
	const qc = useQueryClient();
	const [viewBank, setViewBank] = (0, import_react.useState)(null);
	const { data: bankDetail, isLoading: loadingDetail } = useQuery({
		queryKey: ["bank-questions", viewBank],
		queryFn: () => api.getBankQuestions(viewBank),
		enabled: !!viewBank
	});
	const deleteBank = useMutation({
		mutationFn: (name) => api.deleteBank(name),
		onSuccess: (r) => {
			setResult(r.ok ? {
				ok: true,
				question_count: 0
			} : {
				ok: false,
				error: r.error ?? "delete failed"
			});
			qc.invalidateQueries({ queryKey: ["question-banks"] });
		},
		onError: (e) => setResult({
			ok: false,
			error: e.message
		})
	});
	const extract = useJob("medrack:extractJob");
	const upload = useMutation({
		mutationFn: async (file) => api.uploadQuestionBank({
			file,
			name: bankName,
			subject: bankSubject,
			version: bankVersion
		}),
		onSuccess: (handle) => {
			setResult(null);
			extract.start(handle.job_id);
		},
		onError: (err) => {
			setResult({
				ok: false,
				error: err.message
			});
		}
	});
	(0, import_react.useEffect)(() => {
		const st = extract.job?.status;
		if (st === "done") {
			const r = extract.job?.result ?? {};
			setResult({
				ok: true,
				question_count: r.bank?.question_count ?? 0,
				error: r.warning ?? void 0
			});
			qc.invalidateQueries({ queryKey: ["question-banks"] });
			setShowUpload(false);
			setPickedFile(null);
			if (fileRef.current) fileRef.current.value = "";
			extract.reset();
		} else if (st === "error") setResult({
			ok: false,
			error: extract.job?.error ?? "Extraction failed."
		});
	}, [extract.job?.status]);
	const extracting = extract.job != null && extract.job.status !== "done" && extract.job.status !== "error";
	const busy = upload.isPending || extracting;
	const banks = data ?? [];
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(AppShell, { children: [
		/* @__PURE__ */ (0, import_jsx_runtime.jsx)(PageHeader, {
			eyebrow: "Library",
			title: "Question Banks",
			description: "Upload a question-bank PDF and the backend extracts the questions and saves them as a regression dataset. The bank then appears in the Workspace's bank selector.",
			actions: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
				onClick: () => setShowUpload(true),
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Upload, { className: "mr-1.5 h-4 w-4" }), " Upload question bank"]
			})
		}),
		result && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "mx-6 mt-4 flex items-center justify-between rounded-md border px-3 py-2 text-[12px] " + (result.ok ? "border-success/30 bg-success/10 text-success" : "border-destructive/30 bg-destructive/10 text-destructive"),
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: result.ok ? `Uploaded bank "${bankName}" · ${result.question_count} questions extracted.` : `Upload failed: ${result.error ?? "unknown error"}` }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
				onClick: () => setResult(null),
				className: "text-current/70 hover:text-current",
				children: "dismiss"
			})]
		}),
		/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "grid gap-4 p-6 md:grid-cols-2 xl:grid-cols-3",
			children: [banks.map((b) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				role: "button",
				tabIndex: 0,
				onClick: () => setViewBank(b.name),
				onKeyDown: (e) => {
					if (e.key === "Enter" || e.key === " ") setViewBank(b.name);
				},
				className: "surface-card group relative flex cursor-pointer flex-col gap-3 p-5 transition-colors hover:bg-surface-2 hover:ring-1 hover:ring-primary/30",
				title: "Click to view the questions in this bank",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-start justify-between",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "grid h-10 w-10 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Library, { className: "h-5 w-5" })
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "flex items-center gap-1.5",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(StatusBadge, {
								tone: "primary",
								children: b.subject.toUpperCase()
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
								title: "Delete this question bank",
								className: "rounded p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100",
								onClick: (e) => {
									e.stopPropagation();
									if (confirm(`Delete question bank "${b.name}"? This cannot be undone.`)) deleteBank.mutate(b.name);
								},
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Trash2, { className: "h-3.5 w-3.5" })
							})]
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "font-display text-base font-semibold tracking-tight",
						children: b.name
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "font-mono text-[11px] text-muted-foreground",
						children: b.version
					})] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-auto flex items-baseline gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-mono text-2xl font-semibold tabular-nums",
							children: b.question_count
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "text-xs text-muted-foreground",
							children: "questions"
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-center gap-1 text-[11px] text-primary/80",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Eye, { className: "h-3 w-3" }), " View questions"]
					})
				]
			}, b.name)), banks.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card col-span-full flex flex-col items-center justify-center gap-3 p-10 text-center",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "grid h-12 w-12 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/20",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Library, { className: "h-6 w-6" })
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "font-display text-base font-semibold",
						children: "No question banks yet"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 max-w-md text-sm text-muted-foreground",
						children: "Upload a question-bank PDF. The backend extracts the questions using the same module-extraction pipeline it uses for module ingestion and persists the bank as JSON."
					})] }),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
						onClick: () => setShowUpload(true),
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(FileUp, { className: "mr-1.5 h-4 w-4" }), " Upload question bank"]
					})
				]
			})]
		}),
		viewBank && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4",
			onClick: () => setViewBank(null),
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card flex max-h-[85vh] w-full max-w-2xl flex-col p-6",
				onClick: (e) => e.stopPropagation(),
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "flex items-start justify-between",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
							className: "text-lg font-semibold",
							children: viewBank
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "text-xs text-muted-foreground",
							children: bankDetail ? `${bankDetail.questions.length} questions · ${(bankDetail.subject || "").toUpperCase()}` : "Loading…"
						})] }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
							onClick: () => setViewBank(null),
							className: "rounded p-1 text-muted-foreground hover:bg-background hover:text-foreground",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(X, { className: "h-4 w-4" })
						})]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-4 min-h-0 flex-1 overflow-y-auto",
						children: [
							loadingDetail && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
								className: "text-sm text-muted-foreground",
								children: "Loading questions…"
							}),
							bankDetail && bankDetail.questions.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
								className: "rounded-md border border-border bg-surface px-3 py-4 text-sm text-muted-foreground",
								children: "This bank has no extracted questions. Theory-question extraction needs the LLM — re-upload if it was extracted before the LLM was configured."
							}),
							bankDetail && bankDetail.questions.length > 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("ol", {
								className: "space-y-2",
								children: bankDetail.questions.map((q, i) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("li", {
									className: "rounded-md border border-border bg-surface px-3 py-2 text-sm",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
										className: "flex items-start gap-2",
										children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
											className: "mt-0.5 font-mono text-[11px] text-muted-foreground",
											children: [i + 1, "."]
										}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
											className: "min-w-0",
											children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
												className: "text-foreground",
												children: q.question_text
											}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
												className: "mt-1 flex flex-wrap gap-2 text-[10px] text-muted-foreground",
												children: [
													q.marks ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: [q.marks, " marks"] }) : null,
													q.section ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["· ", q.section] }) : null,
													q.type ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", { children: ["· ", q.type] }) : null
												]
											})]
										})]
									})
								}, q.qid || i))
							})
						]
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-4 flex justify-end",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							variant: "outline",
							onClick: () => setViewBank(null),
							children: "Close"
						})
					})
				]
			})
		}),
		showUpload && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
			className: "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4",
			children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "surface-card max-h-[90vh] w-full max-w-lg overflow-y-auto p-6",
				children: [
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
						className: "text-lg font-semibold",
						children: "Upload question bank"
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-xs text-muted-foreground",
						children: "Select a PDF containing a list of questions (MCQ or theory). The backend runs the module-extraction pipeline and saves the result as a bank."
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-4 space-y-3",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
								label: "Bank name",
								children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
									value: bankName,
									onChange: (e) => setBankName(e.target.value),
									placeholder: "e.g. psm-3rd-year-mock",
									className: "w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
								})
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: "grid grid-cols-1 gap-3 sm:grid-cols-2",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
									label: "Subject",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("select", {
										value: bankSubject,
										onChange: (e) => setBankSubject(e.target.value),
										className: "w-full rounded-md border border-border bg-background px-3 py-2 text-sm",
										children: KNOWN_SUBJECTS.map((s) => /* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
											value: s,
											children: s.toUpperCase()
										}, s))
									})
								}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Field, {
									label: "Version",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
										value: bankVersion,
										onChange: (e) => setBankVersion(e.target.value),
										className: "w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
									})
								})]
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Field, {
								label: "PDF file",
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
									ref: fileRef,
									type: "file",
									accept: "application/pdf",
									onChange: (e) => setPickedFile(e.target.files?.[0] ?? null),
									className: "block w-full cursor-pointer rounded-md border border-dashed border-border bg-background px-3 py-3 text-sm file:mr-3 file:rounded file:border-0 file:bg-primary file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary-foreground hover:border-primary/50"
								}), pickedFile && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
									className: "mt-1 text-[11px] text-muted-foreground",
									children: [
										"Selected: ",
										/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
											className: "font-mono",
											children: pickedFile.name
										}),
										" (",
										Math.round(pickedFile.size / 1024),
										" KB)"
									]
								})]
							})
						]
					}),
					extracting && extract.job && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-4",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ProgressBar, {
							percent: extract.job.percent,
							label: extract.job.message || "Extracting questions…"
						})
					}),
					upload.isError && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive",
						children: upload.error.message
					}),
					/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-6 flex justify-end gap-2",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							variant: "outline",
							onClick: () => {
								setShowUpload(false);
								setPickedFile(null);
								extract.reset();
								if (fileRef.current) fileRef.current.value = "";
							},
							disabled: upload.isPending,
							children: extracting ? "Close" : "Cancel"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							onClick: () => pickedFile && upload.mutate(pickedFile),
							disabled: !pickedFile || !bankName.trim() || busy,
							children: busy ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Upload, { className: "mr-1.5 h-4 w-4 animate-pulse" }), " Extracting…"] }) : /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Upload, { className: "mr-1.5 h-4 w-4" }), " Upload & extract"] })
						})]
					})
				]
			})
		}),
		banks.length > 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "px-6 pb-6 text-[10px] text-muted-foreground",
			children: ["Last refreshed at ", formatTimestamp((/* @__PURE__ */ new Date()).toISOString())]
		})
	] });
}
function Field({ label, children }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
		className: "block",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "mb-1 block text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
			children: label
		}), children]
	});
}
//#endregion
export { QuestionBanksPage as component };
