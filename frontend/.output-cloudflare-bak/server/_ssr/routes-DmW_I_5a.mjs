import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { a as require_jsx_runtime, n as useQuery, t as useMutation } from "../_libs/react+tanstack__react-query.mjs";
import { N as CircleCheck, O as Sparkles, _ as FileText, c as RotateCcw, d as Play, k as LoaderCircle, p as Library, y as Download } from "../_libs/lucide-react.mjs";
import { n as api, r as cn, t as AppShell } from "./app-shell-1ZudwU0b.mjs";
import { t as AnswerViewer } from "./answer-viewer-BGqvZDob.mjs";
import { t as Button } from "./button-7WHCBcnq.mjs";
import { n as useJob, t as ProgressBar } from "./use-job-DrhZwuCz.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/routes-DmW_I_5a.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function usePersistedNumber(key, fallback) {
	const [value, setValue] = (0, import_react.useState)(() => {
		try {
			const v = localStorage.getItem(key);
			if (v != null && v !== "") return Number(v);
		} catch {}
		return fallback;
	});
	(0, import_react.useEffect)(() => {
		try {
			localStorage.setItem(key, String(value));
		} catch {}
	}, [key, value]);
	return [value, setValue];
}
var SELECT_CLS = "mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary";
function Workspace() {
	const [bankName, setBankName] = (0, import_react.useState)("");
	const [bookId, setBookId] = (0, import_react.useState)("");
	const [words10, setWords10] = usePersistedNumber("medrack:words10_v2", 750);
	const [words5, setWords5] = usePersistedNumber("medrack:words5_v2", 375);
	const [words3, setWords3] = usePersistedNumber("medrack:words3_v2", 125);
	const [selMarks, setSelMarks] = (0, import_react.useState)(() => /* @__PURE__ */ new Set([
		10,
		5,
		3
	]));
	const [selChapters, setSelChapters] = (0, import_react.useState)(() => /* @__PURE__ */ new Set());
	const [result, setResult] = (0, import_react.useState)(null);
	const [error, setError] = (0, import_react.useState)(null);
	const [downloadingPdf, setDownloadingPdf] = (0, import_react.useState)(false);
	const [downloadingSolved, setDownloadingSolved] = (0, import_react.useState)(false);
	const autoDownload = (0, import_react.useRef)(false);
	const { data: banks } = useQuery({
		queryKey: ["question-banks"],
		queryFn: () => api.listQuestionBanks()
	});
	const { data: books } = useQuery({
		queryKey: ["books"],
		queryFn: () => api.listBooks()
	});
	const { data: bankDetail } = useQuery({
		queryKey: ["bank-questions", bankName],
		queryFn: () => api.getBankQuestions(bankName),
		enabled: !!bankName
	});
	const resolveMarks = (m) => m === 3 || m === 5 || m === 10 ? m : 10;
	const chapters = (0, import_react.useMemo)(() => {
		const set = /* @__PURE__ */ new Set();
		for (const q of bankDetail?.questions ?? []) {
			const c = (q.chapter ?? "").trim();
			if (c && c.toLowerCase() !== "unknown") set.add(c);
		}
		return [...set];
	}, [bankDetail]);
	(0, import_react.useEffect)(() => {
		setSelChapters(new Set(chapters));
	}, [chapters.join("|")]);
	const marksCount = (0, import_react.useMemo)(() => {
		const c = {
			3: 0,
			5: 0,
			10: 0
		};
		for (const q of bankDetail?.questions ?? []) c[resolveMarks(q.marks)] += 1;
		return c;
	}, [bankDetail]);
	const firstQuestion = (0, import_react.useMemo)(() => (bankDetail?.questions ?? []).filter((q) => {
		if (!selMarks.has(resolveMarks(q.marks))) return false;
		if (chapters.length > 0 && !selChapters.has((q.chapter ?? "").trim())) return false;
		return true;
	}), [
		bankDetail,
		selMarks,
		selChapters,
		chapters.length
	])[0];
	const previewMarks = firstQuestion?.marks === 3 ? 3 : firstQuestion?.marks === 5 ? 5 : 10;
	const previewWords = previewMarks === 3 ? words3 : previewMarks === 5 ? words5 : words10;
	const toggleMark = (m) => setSelMarks((prev) => {
		const next = new Set(prev);
		if (next.has(m)) next.delete(m);
		else next.add(m);
		return next;
	});
	const toggleChapter = (c) => setSelChapters((prev) => {
		const next = new Set(prev);
		if (next.has(c)) next.delete(c);
		else next.add(c);
		return next;
	});
	const allChaptersOn = chapters.length > 0 && selChapters.size === chapters.length;
	const indexedBooks = (0, import_react.useMemo)(() => (books ?? []).filter((b) => b.indexed), [books]);
	const subject = (0, import_react.useMemo)(() => books?.find((b) => b.book_id === bookId), [books, bookId])?.subject || bankDetail?.subject || "psm";
	const preview = useMutation({
		mutationFn: () => {
			if (!bankName) throw new Error("Select a question module first.");
			if (!firstQuestion) throw new Error("This module has no questions to preview yet.");
			return api.generate({
				qid: firstQuestion.qid,
				question_text: firstQuestion.question_text,
				subject,
				marks: previewMarks,
				question_type: firstQuestion.type || "theory",
				book_id: bookId || void 0,
				word_count_target: previewWords
			});
		},
		onSuccess: (data) => {
			setResult(data);
			setError(data.ok ? null : data.error || "Generation failed.");
		},
		onError: (e) => setError(e.message)
	});
	const solve = useJob("medrack:solveJob");
	const solveMutation = useMutation({
		mutationFn: () => {
			if (!bankName) throw new Error("Select a question module first.");
			return api.solveBank({
				name: bankName,
				subject,
				book_id: bookId || void 0,
				marks: 10,
				words_3: words3,
				words_5: words5,
				words_10: words10,
				marks_filter: [...selMarks],
				chapters: chapters.length > 0 ? [...selChapters] : void 0
			});
		},
		onSuccess: (h) => {
			autoDownload.current = true;
			solve.start(h.job_id);
		},
		onError: (e) => setError(e.message)
	});
	const downloadSolvedPdf = async () => {
		if (!solve.job) return;
		setDownloadingSolved(true);
		setError(null);
		try {
			const r = solve.job.result ?? {};
			const res = await fetch(api.jobPdfUrl(solve.job.job_id));
			if (!res.ok) throw new Error(`${res.status}`);
			const blob = await res.blob();
			const u = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = u;
			a.download = r.download_name || `${bankName || "module"}-solved.pdf`;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(u);
		} catch (e) {
			setError(`Solved PDF download failed: ${e.message}`);
		} finally {
			setDownloadingSolved(false);
		}
	};
	(0, import_react.useEffect)(() => {
		if (solve.job?.status === "done" && autoDownload.current) {
			autoDownload.current = false;
			downloadSolvedPdf();
		} else if (solve.job?.status === "error") setError(solve.job.error ?? "Solving the module failed.");
	}, [solve.job?.status]);
	const solving = solve.job != null && solve.job.status !== "done" && solve.job.status !== "error";
	const solveDone = solve.job?.status === "done";
	const solvedInfo = solve.job?.result ?? {};
	const downloadPreviewPdf = async () => {
		if (!result?.answer_text) return;
		setDownloadingPdf(true);
		setError(null);
		try {
			const blob = await api.renderAnswerPdf({
				qid: result.qid,
				subject,
				question_text: firstQuestion?.question_text || "",
				answer_text: result.answer_text,
				marks: previewMarks,
				question_type: firstQuestion?.type || "theory"
			});
			const u = URL.createObjectURL(blob);
			const a = document.createElement("a");
			a.href = u;
			a.download = `medrack-${result.qid}.pdf`;
			document.body.appendChild(a);
			a.click();
			a.remove();
			URL.revokeObjectURL(u);
		} catch (e) {
			setError(e.message);
		} finally {
			setDownloadingPdf(false);
		}
	};
	const wordCount = (0, import_react.useMemo)(() => result?.answer_text?.trim().split(/\s+/).filter(Boolean).length ?? 0, [result]);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)(AppShell, { children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex min-h-0 flex-col lg:grid lg:h-full lg:grid-cols-[360px_minmax(0,1fr)]",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("aside", {
			className: "flex flex-col gap-4 border-b border-border bg-surface p-4 sm:p-5 lg:min-h-0 lg:overflow-y-auto lg:border-b-0 lg:border-r",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h1", {
					className: "font-display text-lg font-semibold",
					children: "Generate Answers"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-1 text-xs text-muted-foreground",
					children: "Pick a question module and a textbook, set the answer lengths, preview one answer — then approve to solve the whole module into a PDF."
				})] }),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Field, {
					label: "1 · Question module",
					hint: bankDetail ? `${bankDetail.questions.length} questions` : void 0,
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("select", {
						value: bankName,
						onChange: (e) => {
							setBankName(e.target.value);
							setResult(null);
							setError(null);
						},
						className: SELECT_CLS,
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
							value: "",
							children: "Select a question module…"
						}), (banks ?? []).map((b) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("option", {
							value: b.name,
							children: [
								b.name,
								" · ",
								b.subject.toUpperCase(),
								" · ",
								b.question_count,
								" Qs"
							]
						}, b.name))]
					}), banks && banks.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-[11px] text-warning",
						children: "No modules yet — upload one on the Question Banks page."
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Field, {
					label: "2 · Textbook (knowledge base)",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("select", {
						value: bookId,
						onChange: (e) => setBookId(e.target.value),
						className: SELECT_CLS,
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("option", {
							value: "",
							children: "Auto — all books in the module's subject"
						}), indexedBooks.map((b) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("option", {
							value: b.book_id,
							children: [
								b.title,
								" · ",
								b.subject.toUpperCase(),
								" · ",
								b.chunk_count,
								" chunks"
							]
						}, b.book_id))]
					}), books && indexedBooks.length === 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-[11px] text-warning",
						children: "No indexed books — upload a textbook on the Books page."
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Field, {
					label: "3 · Marks to include",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-1 flex gap-2",
						children: [
							10,
							5,
							3
						].map((m) => {
							const on = selMarks.has(m);
							const n = marksCount[m] ?? 0;
							return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
								type: "button",
								onClick: () => toggleMark(m),
								"aria-pressed": on,
								className: cn("flex-1 rounded-md border px-2 py-2 text-xs font-medium transition-colors", on ? "border-primary bg-primary/15 text-primary" : "border-border bg-background text-muted-foreground hover:bg-surface-2"),
								children: [
									m,
									"-mark",
									bankName ? ` (${n})` : ""
								]
							}, m);
						})
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-[10px] text-muted-foreground",
						children: "Only ticked marks are produced. Select more than one to combine them."
					})]
				}),
				chapters.length > 0 && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Field, {
					label: "4 · Chapters",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mb-1 mt-1 flex items-center justify-between",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
							className: "text-[10px] text-muted-foreground",
							children: [
								selChapters.size,
								"/",
								chapters.length,
								" selected"
							]
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
							type: "button",
							onClick: () => setSelChapters(allChaptersOn ? /* @__PURE__ */ new Set() : new Set(chapters)),
							className: "text-[10px] font-medium text-primary hover:underline",
							children: allChaptersOn ? "Clear all" : "Select all"
						})]
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "max-h-44 space-y-1 overflow-y-auto rounded-md border border-border bg-background p-2",
						children: chapters.map((c) => /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
							className: "flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-xs hover:bg-surface-2",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
								type: "checkbox",
								checked: selChapters.has(c),
								onChange: () => toggleChapter(c),
								className: "h-3.5 w-3.5 shrink-0 accent-primary"
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "min-w-0 truncate",
								children: c
							})]
						}, c))
					})]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Field, {
					label: `${chapters.length > 0 ? "5" : "4"} · Answer length (words)`,
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "mt-1 grid grid-cols-3 gap-2",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(LengthBox, {
								label: "10-mark",
								value: words10,
								onChange: setWords10
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(LengthBox, {
								label: "5-mark",
								value: words5,
								onChange: setWords5
							}),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(LengthBox, {
								label: "3-mark",
								value: words3,
								onChange: setWords3
							})
						]
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
						className: "mt-1 text-[10px] text-muted-foreground",
						children: "Each question is answered at the length for its own marks."
					})]
				}),
				firstQuestion && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "rounded-md border border-border bg-background px-3 py-2 text-[11px] text-muted-foreground",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("span", {
							className: "font-medium text-foreground",
							children: [
								"Preview (",
								previewMarks,
								"-mark → ",
								previewWords,
								" words):"
							]
						}),
						" ",
						firstQuestion.question_text.slice(0, 120),
						firstQuestion.question_text.length > 120 ? "…" : ""
					]
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "mt-1 space-y-2",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							className: "w-full",
							onClick: () => {
								setError(null);
								preview.mutate();
							},
							disabled: !bankName || !firstQuestion || preview.isPending || solving,
							children: preview.isPending ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(LoaderCircle, { className: "mr-2 h-4 w-4 animate-spin" }), " Generating preview…"] }) : /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Play, { className: "mr-2 h-4 w-4" }), " Generate Preview Answer"] })
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Button, {
							className: "w-full bg-success text-success-foreground hover:bg-success/90",
							onClick: () => {
								setError(null);
								solveMutation.mutate();
							},
							disabled: !result?.answer_text || solving || solveMutation.isPending || selMarks.size === 0 || chapters.length > 0 && selChapters.size === 0,
							title: "Generate answers for the selected marks and chapters, and download one PDF",
							children: solving ? /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(LoaderCircle, { className: "mr-2 h-4 w-4 animate-spin" }), " Solving module…"] }) : /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(import_jsx_runtime.Fragment, { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(CircleCheck, { className: "mr-2 h-4 w-4" }), " Approve & Solve Module"] })
						}),
						solving && solve.job && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(ProgressBar, {
							percent: solve.job.percent,
							label: solve.job.message || "Solving…"
						}),
						solveDone && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "rounded-md border border-success/30 bg-success/10 px-3 py-2 text-[12px] text-success",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: "mb-1.5 font-medium",
								children: [
									"Module solved — ",
									solvedInfo.answered ?? "?",
									"/",
									solvedInfo.questions_total ?? "?",
									" ",
									"answered."
								]
							}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
								size: "sm",
								variant: "outline",
								className: "w-full",
								onClick: downloadSolvedPdf,
								disabled: downloadingSolved,
								children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Download, { className: "mr-1.5 h-3.5 w-3.5" }), downloadingSolved ? "Downloading…" : "Download Again"]
							})]
						}),
						error && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
							className: "rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive",
							children: error
						})
					]
				})
			]
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("section", {
			className: "flex flex-col lg:min-h-0",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex items-center justify-between gap-2 border-b border-border px-4 py-3 sm:px-6",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex min-w-0 items-center gap-3",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "grid h-9 w-9 shrink-0 place-items-center rounded-md bg-primary/10 text-primary ring-1 ring-primary/30",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(FileText, { className: "h-4 w-4" })
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "min-w-0",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "truncate font-display text-[15px] font-semibold",
							children: result ? "Preview answer" : "Answer preview"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "truncate text-[11px] text-muted-foreground",
							children: result ? `${wordCount} words · ${result.token_count} tokens · ${result.latency_seconds.toFixed(1)}s` : "Generate a preview to see a formatted answer"
						})]
					})]
				}), result?.answer_text && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Button, {
					variant: "outline",
					size: "sm",
					onClick: downloadPreviewPdf,
					disabled: downloadingPdf,
					title: "Download this preview answer as a PDF",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Download, { className: "mr-1.5 h-3.5 w-3.5" }),
						" ",
						downloadingPdf ? "PDF…" : "PDF"
					]
				})]
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "min-h-[55vh] flex-1 overflow-auto bg-background lg:min-h-0",
				children: [
					preview.isPending && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "grid h-full place-items-center",
						children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "text-center",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
									className: "mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-primary/10 text-primary ring-1 ring-primary/30",
									children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(LoaderCircle, { className: "h-5 w-5 animate-spin" })
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
									className: "text-sm font-medium",
									children: "Synthesizing answer"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
									className: "mt-1 text-xs text-muted-foreground",
									children: "Retrieving from the textbook → writing the answer"
								})
							]
						})
					}),
					!preview.isPending && result?.answer_text && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "flex items-center gap-2 border-b border-border bg-success/10 px-4 py-2 text-[12px] text-success sm:px-6",
							children: [
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Sparkles, { className: "h-3.5 w-3.5" }),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "font-medium",
									children: "Preview ready"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
									className: "text-success/70",
									children: "·"
								}),
								/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { children: "approve on the left to solve the whole module into a PDF" })
							]
						}),
						firstQuestion && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "mx-auto max-w-[80ch] px-4 pt-6 sm:px-8",
							children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
								className: "rounded-md bg-primary px-4 py-3 text-sm font-semibold leading-snug text-primary-foreground",
								children: ["Q. ", firstQuestion.question_text]
							})
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(AnswerViewer, { answer: result.answer_text })
					] }),
					!preview.isPending && result && !result.answer_text && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(CenterMessage, {
						title: "No answer produced",
						body: result.error ?? "The backend returned an empty answer."
					}),
					!preview.isPending && !result && /* @__PURE__ */ (0, import_jsx_runtime.jsx)(EmptyState, { hasSolve: !!solve.job })
				]
			})]
		})]
	}) });
}
function LengthBox({ label, value, onChange }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("label", {
		className: "rounded-md border border-border bg-background px-3 py-2",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "block text-[11px] font-medium text-foreground",
			children: label
		}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "mt-1 flex items-baseline gap-1",
			children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("input", {
				type: "number",
				min: 50,
				max: 3e3,
				step: 25,
				value,
				onChange: (e) => {
					const n = Number(e.target.value);
					if (!Number.isNaN(n)) onChange(Math.max(50, Math.min(3e3, n)));
				},
				className: "w-full bg-transparent font-mono text-lg font-semibold tabular-nums outline-none"
			}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
				className: "text-[10px] text-muted-foreground",
				children: "words"
			})]
		})]
	});
}
function Field({ label, hint, children }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex items-center justify-between",
		children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("label", {
			className: "text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
			children: label
		}), hint ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
			className: "text-[10px] text-muted-foreground",
			children: hint
		}) : null]
	}), children] });
}
function CenterMessage({ title, body }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "grid h-full place-items-center px-6",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "max-w-md text-center",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "mx-auto mb-3 grid h-10 w-10 place-items-center rounded-full bg-warning/10 text-warning ring-1 ring-warning/30",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Sparkles, { className: "h-5 w-5" })
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "font-display text-lg font-semibold",
					children: title
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("p", {
					className: "mt-1 text-sm text-muted-foreground",
					children: body
				})
			]
		})
	});
}
function EmptyState({ hasSolve }) {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
		className: "grid h-full place-items-center px-6",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
			className: "max-w-md text-center",
			children: [
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/30",
					children: hasSolve ? /* @__PURE__ */ (0, import_jsx_runtime.jsx)(RotateCcw, { className: "h-5 w-5" }) : /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Library, { className: "h-5 w-5" })
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsx)("h2", {
					className: "font-display text-lg font-semibold",
					children: hasSolve ? "Your last solve is on the left" : "Solve a question module"
				}),
				/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("p", {
					className: "mx-auto mt-2 max-w-sm text-sm text-muted-foreground",
					children: [
						"Choose a question module and a textbook on the left, set the answer lengths, and click",
						" ",
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "font-medium text-foreground",
							children: "Generate Preview Answer"
						}),
						". Approve it to solve every question in the module and download one PDF."
					]
				})
			]
		})
	});
}
//#endregion
export { Workspace as component };
