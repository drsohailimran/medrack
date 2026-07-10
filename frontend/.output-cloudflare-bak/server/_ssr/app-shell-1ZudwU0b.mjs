import { n as __toESM } from "../_runtime.mjs";
import { n as require_react } from "../_libs/@radix-ui/react-compose-refs+[...].mjs";
import { g as Link, l as useRouterState } from "../_libs/@tanstack/react-router+[...].mjs";
import { a as require_jsx_runtime, n as useQuery } from "../_libs/react+tanstack__react-query.mjs";
import { M as CircleQuestionMark, O as Sparkles, T as BookOpen, a as Settings, b as Database, f as Menu, o as Search, p as Library, s as ScrollText, x as Command } from "../_libs/lucide-react.mjs";
import { n as clsx } from "../_libs/class-variance-authority+clsx.mjs";
import { t as twMerge } from "../_libs/tailwind-merge.mjs";
//#region node_modules/.nitro/vite/services/ssr/assets/app-shell-1ZudwU0b.js
var import_react = /* @__PURE__ */ __toESM(require_react());
var import_jsx_runtime = require_jsx_runtime();
function cn(...inputs) {
	return twMerge(clsx(inputs));
}
var versionInfo = {
	schema_version: 1,
	package_version: "0.3.0-backend-freeze",
	pipeline_versions: {
		schema: 2,
		prompt: 1,
		retrieval: 1,
		planner: 0,
		validator: 0,
		reranker: 0,
		renderer: 1
	},
	benchmark_baseline_tag: "phase-5-baseline"
};
var books = [
	{
		schema_version: 1,
		book_id: "park_psm_v4",
		title: "Park's Textbook of Preventive and Social Medicine",
		subject: "psm",
		path: "/home/user/.medrack/inbox/park_psm_v4.pdf",
		indexed: true,
		indexed_at: "2025-01-15T10:30:00",
		chunk_count: 1234
	},
	{
		schema_version: 1,
		book_id: "park_fmt_v3",
		title: "Park's Textbook of Forensic Medicine & Toxicology",
		subject: "fmt",
		path: "/home/user/.medrack/inbox/park_fmt_v3.pdf",
		indexed: true,
		indexed_at: "2025-01-20T14:15:00",
		chunk_count: 876
	},
	{
		schema_version: 1,
		book_id: "kpark_clinical",
		title: "K. Park Clinical PSM Companion",
		subject: "psm",
		path: "/home/user/.medrack/inbox/kpark_clinical.pdf",
		indexed: false,
		indexed_at: null,
		chunk_count: 0
	},
	{
		schema_version: 1,
		book_id: "reddy_fmt",
		title: "Essentials of Forensic Medicine — Reddy",
		subject: "fmt",
		path: "/home/user/.medrack/inbox/reddy_fmt.pdf",
		indexed: true,
		indexed_at: "2025-02-02T09:12:00",
		chunk_count: 642
	}
];
var questionBanks = [
	{
		schema_version: 1,
		name: "PSM Regression v1",
		version: "v1",
		subject: "psm",
		path: "/home/user/.medrack/tests/regression_datasets/v1.json",
		question_count: 20
	},
	{
		schema_version: 1,
		name: "FMT Regression v1",
		version: "v1",
		subject: "fmt",
		path: "/home/user/.medrack/tests/regression_datasets/fmt_v1.json",
		question_count: 12
	},
	{
		schema_version: 1,
		name: "NEET PG Mock 2024",
		version: "2024-01",
		subject: "psm",
		path: "/home/user/.medrack/tests/regression_datasets/neet_pg_2024.json",
		question_count: 45
	}
];
var projects = [{
	id: "prj-neet-pg-2026",
	name: "NEET PG 2026 Prep",
	subject: "psm",
	description: "Long-answer practice across PSM modules 1–8.",
	question_count: 42,
	created_at: "2025-12-01T08:00:00",
	updated_at: "2026-06-20T11:32:00"
}, {
	id: "prj-university-finals",
	name: "University Finals — FMT",
	subject: "fmt",
	description: "10-mark and 5-mark essays covering toxicology and forensic pathology.",
	question_count: 18,
	created_at: "2026-02-10T14:00:00",
	updated_at: "2026-06-15T09:11:00"
}];
var ingestionStatuses = {
	park_psm_v4: {
		schema_version: 1,
		book_id: "park_psm_v4",
		status: "succeeded",
		started_at: "2025-01-15T10:25:00",
		finished_at: "2025-01-15T10:30:00",
		chunk_count: 1234,
		error: null
	},
	kpark_clinical: {
		schema_version: 1,
		book_id: "kpark_clinical",
		status: "running",
		started_at: "2026-06-29T09:00:00",
		finished_at: null,
		chunk_count: 0,
		error: null
	}
};
var sampleAnswer = `Introduction: Diabetes mellitus is a chronic metabolic disorder characterized by sustained hyperglycemia resulting from defects in insulin secretion, insulin action, or both. It represents one of the leading non-communicable disease burdens of the 21st century, with India bearing a disproportionate share of cases.

Definition: According to the World Health Organization, diabetes mellitus is a group of metabolic diseases defined by chronically elevated blood glucose. Diagnostic thresholds include fasting plasma glucose ≥ 126 mg/dL, 2-hour plasma glucose ≥ 200 mg/dL on OGTT, or HbA1c ≥ 6.5%. [chunk_park_dm_001]

Epidemiology: The global prevalence of diabetes rose from 108 million in 1980 to over 537 million in 2021. India hosts an estimated 77 million adults with diabetes — second only to China — with projections reaching 134 million by 2045. Type 2 diabetes accounts for 90–95% of all cases; urban prevalence (11.2%) exceeds rural prevalence (5.2%). [chunk_park_dm_004]

Etiology: Type 2 diabetes is driven by insulin resistance compounded by progressive beta-cell dysfunction. Key risk factors include obesity (especially central adiposity), physical inactivity, family history, increasing age, gestational diabetes, and ethnicity. [chunk_park_dm_007]

Management: Management rests on four pillars — lifestyle modification, pharmacotherapy, monitoring, and prevention of complications.

1. Lifestyle modification: medical nutrition therapy, ≥150 minutes/week moderate aerobic activity, weight reduction of 5–10%, smoking cessation.
2. Pharmacotherapy: First-line is metformin 500 mg twice daily, titrated to 2 g/day. Add SGLT2 inhibitors or GLP-1 agonists for patients with cardiovascular or renal risk. Insulin is reserved for severe hyperglycemia or when oral agents fail. [chunk_park_dm_011]
3. Monitoring: HbA1c every 3 months until target (<7%) is achieved, then biannually. Annual eye, foot, and renal screening.
4. Prevention of complications: blood pressure <130/80 mmHg, LDL <70 mg/dL, ACE inhibitor or ARB for proteinuria. [chunk_park_dm_015]

Conclusion: Diabetes mellitus requires lifelong, multi-disciplinary management. Early diagnosis, sustained lifestyle change, evidence-based pharmacotherapy, and structured screening for complications remain the cornerstones of reducing morbidity and mortality.`;
var generationResultSuccess = {
	schema_version: 1,
	qid: "q001",
	ok: true,
	answer_text: sampleAnswer,
	pdf_path: "/home/user/.medrack/cache/psm-module-1/diabetes/q001.pdf",
	cache_hit: false,
	error: null,
	token_count: 1234,
	latency_seconds: 5.6
};
var pipelineTrace = {
	schema_version: 1,
	qid: "q001",
	stages: [
		{
			schema_version: 1,
			stage: "planner",
			output: {
				subject: "psm",
				marks: 10,
				question_type: "theory",
				target_word_count: 775,
				sections: [
					{
						name: "introduction",
						target_word_count: 116,
						required: true,
						category: "framing"
					},
					{
						name: "definition",
						target_word_count: 150,
						required: true,
						category: "medical",
						metadata_section: "section_definition"
					},
					{
						name: "epidemiology",
						target_word_count: 150,
						required: true,
						category: "medical",
						metadata_section: "section_epidemiology"
					},
					{
						name: "management",
						target_word_count: 290,
						required: true,
						category: "medical",
						metadata_section: "section_management"
					},
					{
						name: "conclusion",
						target_word_count: 78,
						required: true,
						category: "framing"
					}
				],
				required_metadata_categories: [
					"section_definition",
					"section_epidemiology",
					"section_management"
				]
			},
			latency_seconds: .001
		},
		{
			schema_version: 1,
			stage: "blueprint",
			output: {
				subject: "psm",
				marks: 10,
				total_target_word_count: 775,
				section_specs: [
					{
						section_name: "introduction",
						priority: 0,
						min_chunks: 1,
						max_chunks: 3,
						evidence_category: "framing"
					},
					{
						section_name: "definition",
						priority: 0,
						min_chunks: 1,
						max_chunks: 3,
						evidence_category: "medical",
						metadata_filter: { section_definition: true }
					},
					{
						section_name: "epidemiology",
						priority: 0,
						min_chunks: 1,
						max_chunks: 3,
						evidence_category: "medical",
						metadata_filter: { section_epidemiology: true }
					},
					{
						section_name: "management",
						priority: 0,
						min_chunks: 1,
						max_chunks: 3,
						evidence_category: "medical",
						metadata_filter: { section_management: true }
					},
					{
						section_name: "conclusion",
						priority: 0,
						min_chunks: 1,
						max_chunks: 3,
						evidence_category: "framing"
					}
				],
				aggregate_metadata_filter: { $or: [
					{ section_definition: true },
					{ section_epidemiology: true },
					{ section_management: true }
				] },
				evidence_categories: ["framing", "medical"]
			},
			latency_seconds: .001
		},
		{
			schema_version: 1,
			stage: "retrieval",
			output: {
				strategy: "AdaptiveStrategy",
				top_k_by_marks: {
					"5": 5,
					"10": 8,
					"15": 10
				}
			},
			latency_seconds: .012
		},
		{
			schema_version: 1,
			stage: "reranker",
			output: {
				metadata_reranker: "MetadataBoostReranker",
				semantic_reranker_options: ["IdentityReranker", "HeuristicReranker"],
				default_semantic_reranker: "IdentityReranker"
			},
			latency_seconds: .003
		},
		{
			schema_version: 1,
			stage: "writer",
			output: {
				theory_long_target_words: 775,
				theory_short_target_words: 475
			},
			latency_seconds: 4.32
		},
		{
			schema_version: 1,
			stage: "validator",
			output: {
				rule_count: 9,
				rule_names: [
					"FormattingRule",
					"HeadingStructureRule",
					"DuplicateSectionRule",
					"EmptySectionRule",
					"WordCountRule",
					"RequiredSectionsRule",
					"BlueprintComplianceRule",
					"EvidenceCoverageRule",
					"ReferenceConsistencyRule"
				]
			},
			latency_seconds: .008
		}
	],
	total_latency_seconds: 4.356
};
var validationReportPass = {
	schema_version: 1,
	pass: true,
	score: .94,
	results: [
		{
			rule_name: "FormattingRule",
			severity: "pass",
			message: "Formatting OK",
			details: null
		},
		{
			rule_name: "HeadingStructureRule",
			severity: "pass",
			message: "Found 6 section heading(s)",
			details: null
		},
		{
			rule_name: "DuplicateSectionRule",
			severity: "pass",
			message: "No duplicate sections",
			details: null
		},
		{
			rule_name: "EmptySectionRule",
			severity: "pass",
			message: "No empty sections",
			details: null
		},
		{
			rule_name: "WordCountRule",
			severity: "warn",
			message: "1 section close to upper bound",
			details: { offending: [{
				section: "management",
				target: 290,
				actual: 316
			}] }
		},
		{
			rule_name: "RequiredSectionsRule",
			severity: "pass",
			message: "All 5 required section(s) present",
			details: null
		},
		{
			rule_name: "BlueprintComplianceRule",
			severity: "pass",
			message: "All blueprint sections present",
			details: null
		},
		{
			rule_name: "EvidenceCoverageRule",
			severity: "pass",
			message: "Found references in 5/5 medical section(s)",
			details: null
		},
		{
			rule_name: "ReferenceConsistencyRule",
			severity: "pass",
			message: "All chunk references are unique within sections",
			details: null
		}
	],
	failed_rules: [],
	warnings: ["WordCountRule"],
	informational_messages: [
		"[FormattingRule] Formatting OK",
		"[HeadingStructureRule] Found 6 section heading(s)",
		"[EvidenceCoverageRule] Found references in 5/5 medical section(s)"
	]
};
var benchmarkRuns = [
	{
		schema_version: 1,
		run_id: "20260628T193408Z",
		timestamp: "2026-06-28T19:34:08Z",
		llm_mode: "real",
		n_questions: 20,
		n_success: 40,
		n_failure: 0,
		cache_hit_rate: .55,
		total_tokens: 18420,
		avg_total_latency_seconds: 6.34,
		avg_pdf_generation_seconds: .121,
		json_report_path: "/home/user/.medrack/benchmarks/runs/20260628T193408Z_run.json",
		markdown_report_path: "/home/user/.medrack/benchmarks/runs/20260628T193408Z_report.md"
	},
	{
		schema_version: 1,
		run_id: "20260627T100000Z",
		timestamp: "2026-06-27T10:00:00Z",
		llm_mode: "real",
		n_questions: 20,
		n_success: 39,
		n_failure: 1,
		cache_hit_rate: .4,
		total_tokens: 21100,
		avg_total_latency_seconds: 7.21,
		avg_pdf_generation_seconds: .118,
		json_report_path: "/home/user/.medrack/benchmarks/runs/20260627T100000Z_run.json",
		markdown_report_path: "/home/user/.medrack/benchmarks/runs/20260627T100000Z_report.md"
	},
	{
		schema_version: 1,
		run_id: "20260620T084500Z",
		timestamp: "2026-06-20T08:45:00Z",
		llm_mode: "mock",
		n_questions: 20,
		n_success: 40,
		n_failure: 0,
		cache_hit_rate: .5,
		total_tokens: 12e3,
		avg_total_latency_seconds: .169,
		avg_pdf_generation_seconds: .005,
		json_report_path: "/home/user/.medrack/benchmarks/runs/20260620T084500Z_run.json",
		markdown_report_path: null
	}
];
var benchmarkCompare = {
	ok: true,
	run_a: "20260627T100000Z",
	run_b: "20260628T193408Z",
	delta: {
		n_questions: 0,
		n_success: 1,
		n_failure: -1,
		cache_hit_rate: .15,
		total_tokens: -2680,
		avg_total_latency_seconds: -.87
	}
};
var cacheEntries = [
	{
		schema_version: 1,
		qid: "q001",
		subject: "psm",
		is_stale: false,
		stale_reasons: [],
		versions: {
			schema: 2,
			prompt: 1,
			retrieval: 1,
			planner: 0,
			validator: 0,
			reranker: 0,
			renderer: 1,
			embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
		},
		target_word_count: 775,
		cached_at: "2026-06-15T11:00:00",
		last_validated_at: "2026-06-15T11:00:00",
		validation_score: .94
	},
	{
		schema_version: 1,
		qid: "q002",
		subject: "psm",
		is_stale: true,
		stale_reasons: ["schema_version_mismatch"],
		versions: {
			schema: 1,
			prompt: 1,
			retrieval: 1,
			planner: 0,
			validator: 0,
			reranker: 0,
			renderer: 1,
			embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
		},
		target_word_count: 475,
		cached_at: "2025-12-01T10:00:00",
		last_validated_at: "2025-12-01T10:00:00",
		validation_score: .667
	},
	{
		schema_version: 1,
		qid: "q003",
		subject: "psm",
		is_stale: false,
		stale_reasons: [],
		versions: {
			schema: 2,
			prompt: 1,
			retrieval: 1,
			planner: 0,
			validator: 0,
			reranker: 0,
			renderer: 1,
			embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
		},
		target_word_count: 775,
		cached_at: "2026-06-20T13:22:00",
		last_validated_at: "2026-06-20T13:22:00",
		validation_score: .88
	},
	{
		schema_version: 1,
		qid: "q014",
		subject: "fmt",
		is_stale: false,
		stale_reasons: [],
		versions: {
			schema: 2,
			prompt: 1,
			retrieval: 1,
			planner: 0,
			validator: 0,
			reranker: 0,
			renderer: 1,
			embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
		},
		target_word_count: 475,
		cached_at: "2026-06-22T16:40:00",
		last_validated_at: "2026-06-22T16:40:00",
		validation_score: .91
	},
	{
		schema_version: 1,
		qid: "q021",
		subject: "fmt",
		is_stale: true,
		stale_reasons: ["validator_version_bump"],
		versions: {
			schema: 2,
			prompt: 1,
			retrieval: 1,
			planner: 0,
			validator: 0,
			reranker: 0,
			renderer: 1,
			embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
		},
		target_word_count: 775,
		cached_at: "2026-05-30T10:00:00",
		last_validated_at: "2026-05-30T10:00:00",
		validation_score: .71
	}
];
var cacheQuestionTexts = {
	q001: "Discuss the management of diabetes mellitus.",
	q002: "Describe the epidemiology of tuberculosis in India.",
	q003: "What are the national health programmes for vector-borne diseases?",
	q014: "Describe the medico-legal autopsy procedure for a road-traffic fatality.",
	q021: "Discuss the toxicology, clinical features and management of organophosphate poisoning."
};
function getCacheEntryFull(qid) {
	const entry = cacheEntries.find((e) => e.qid === qid);
	if (!entry) return void 0;
	return {
		...entry,
		module: entry.subject === "psm" ? "psm-module-1" : "fmt-module-1",
		chapter: "general",
		question_text: cacheQuestionTexts[qid] ?? "(question text unavailable)",
		answer_text: sampleAnswer,
		pdf_path: `/home/user/.medrack/cache/${entry.subject}/general/${qid}.pdf`,
		stale: entry.is_stale,
		embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
		package_version: "0.3.0-backend-freeze"
	};
}
var cacheStatus = {
	schema_version: 1,
	total_entries: cacheEntries.length,
	by_subject: {
		psm: 3,
		fmt: 2
	},
	stale_by_subject: {
		psm: 1,
		fmt: 1
	}
};
var logs = {
	ingestion: [
		{
			book_id: "park_psm_v4",
			status: "succeeded",
			started_at: "2026-01-15T10:25:00",
			finished_at: "2026-01-15T10:30:00",
			chunk_count: 1234,
			error: null
		},
		{
			book_id: "park_fmt_v3",
			status: "succeeded",
			started_at: "2026-01-20T14:10:00",
			finished_at: "2026-01-20T14:15:00",
			chunk_count: 876,
			error: null
		},
		{
			book_id: "kpark_clinical",
			status: "running",
			started_at: "2026-06-29T09:00:00",
			finished_at: null,
			chunk_count: 0,
			error: null
		}
	],
	generation: [
		{
			qid: "q001",
			subject: "psm",
			ok: true,
			token_count: 1234,
			latency_seconds: 5.6,
			cache_hit: false,
			timestamp: "2026-06-29T10:11:02"
		},
		{
			qid: "q002",
			subject: "psm",
			ok: true,
			token_count: 567,
			latency_seconds: 3.2,
			cache_hit: true,
			timestamp: "2026-06-29T10:14:18"
		},
		{
			qid: "q003",
			subject: "psm",
			ok: true,
			token_count: 1812,
			latency_seconds: 7.4,
			cache_hit: false,
			timestamp: "2026-06-29T10:18:55"
		},
		{
			qid: "q014",
			subject: "fmt",
			ok: true,
			token_count: 988,
			latency_seconds: 4.1,
			cache_hit: false,
			timestamp: "2026-06-29T10:24:01"
		}
	],
	validation: [
		{
			qid: "q001",
			passed: true,
			score: .94,
			rule_count: 9,
			failed_count: 0,
			timestamp: "2026-06-29T10:11:08"
		},
		{
			qid: "q002",
			passed: false,
			score: .5,
			rule_count: 9,
			failed_count: 1,
			timestamp: "2026-06-29T10:14:19"
		},
		{
			qid: "q003",
			passed: true,
			score: .88,
			rule_count: 9,
			failed_count: 0,
			timestamp: "2026-06-29T10:18:59"
		}
	],
	benchmark: [{
		run_id: "20260628T193408Z",
		n_questions: 20,
		n_success: 40,
		n_failure: 0,
		cache_hit_rate: .55,
		total_tokens: 18420,
		llm_mode: "real",
		timestamp: "2026-06-28T19:34:08Z"
	}]
};
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function jitter(min, max) {
	return min + Math.random() * (max - min);
}
var mockApi = {
	async getVersion() {
		await sleep(120);
		return versionInfo;
	},
	async listBooks() {
		await sleep(jitter(140, 260));
		return books;
	},
	async addBook({ subject, book_title }) {
		if (subject !== "psm" && subject !== "fmt") throw new Error("Subject must be psm or fmt");
		await sleep(400);
		const book_id = (book_title ?? "new_book").toLowerCase().replace(/\s+/g, "_");
		return {
			ok: true,
			book_id,
			path: `/home/user/.medrack/inbox/${book_id}.pdf`,
			subject
		};
	},
	async removeBook(book_id) {
		await sleep(200);
		return {
			ok: true,
			book_id,
			moved_to: "/home/user/.medrack/trash"
		};
	},
	async reindexBook(book_id) {
		await sleep(200);
		return {
			ok: true,
			book_id
		};
	},
	async getIngestionStatus(book_id) {
		await sleep(200);
		return ingestionStatuses[book_id] ?? {
			schema_version: 1,
			book_id,
			status: "unknown",
			started_at: (/* @__PURE__ */ new Date()).toISOString(),
			finished_at: null,
			chunk_count: 0,
			error: null
		};
	},
	async listQuestionBanks() {
		await sleep(180);
		return questionBanks;
	},
	async uploadBook({ title }) {
		await sleep(200);
		return {
			job_id: `mock-ingest-${Date.now()}`,
			kind: "ingest_book",
			book_title: title
		};
	},
	async uploadQuestionBank({ name }) {
		await sleep(200);
		return {
			job_id: `mock-extract-${Date.now()}`,
			kind: "extract_bank",
			book_title: name
		};
	},
	async getBankQuestions(name) {
		await sleep(120);
		return {
			name,
			subject: "psm",
			version: "v1",
			questions: []
		};
	},
	async deleteBank(name) {
		await sleep(120);
		return {
			ok: true,
			name
		};
	},
	async getJob(job_id) {
		await sleep(120);
		return {
			schema_version: 1,
			job_id,
			kind: "mock",
			status: "done",
			percent: 100,
			message: "Done",
			result: {
				question_count: 20,
				answered: 20,
				download_name: "mock.pdf"
			},
			error: null
		};
	},
	jobPdfUrl(job_id) {
		return `mock://jobs/${job_id}/pdf`;
	},
	async solveBank({ name }) {
		await sleep(200);
		return {
			job_id: `mock-solve-${Date.now()}`,
			kind: "solve_bank",
			book_title: name
		};
	},
	async renderAnswerPdf() {
		await sleep(200);
		return new Blob(["%PDF-1.4 mock"], { type: "application/pdf" });
	},
	async renderGraphviz() {
		await sleep(120);
		return new Blob([], { type: "image/png" });
	},
	async listProjects() {
		await sleep(140);
		return projects;
	},
	async generate(req) {
		const cacheHit = req.qid === "q001" || req.qid === "q014";
		await sleep(cacheHit ? 250 : 2400);
		return {
			...generationResultSuccess,
			qid: req.qid,
			cache_hit: cacheHit,
			latency_seconds: cacheHit ? .18 : jitter(4.2, 7.8),
			token_count: cacheHit ? 0 : Math.round(jitter(900, 1600))
		};
	},
	async batchGenerate(reqs) {
		const out = [];
		for (const r of reqs) out.push(await mockApi.generate(r));
		return out;
	},
	async revise(qid, req) {
		await sleep(2200);
		return {
			...generationResultSuccess,
			qid,
			cache_hit: false
		};
	},
	async listStale(_module, dry_run = true) {
		await sleep(180);
		const stale = cacheEntries.filter((e) => e.is_stale).map((e) => e.qid);
		return dry_run ? {
			ok: true,
			dry_run: true,
			stale_count: stale.length,
			stale_qids: stale
		} : {
			ok: true,
			dry_run: false,
			reanswered_count: stale.length,
			results: []
		};
	},
	async inspectPipeline({ qid }) {
		await sleep(360);
		return {
			...pipelineTrace,
			qid
		};
	},
	async validate() {
		await sleep(220);
		return validationReportPass;
	},
	async listBenchmarkRuns() {
		await sleep(200);
		return benchmarkRuns;
	},
	async getBenchmarkRun(run_id) {
		const run = benchmarkRuns.find((r) => r.run_id === run_id);
		if (!run) throw new Error(`RUN_NOT_FOUND: ${run_id}`);
		await sleep(160);
		return run;
	},
	async compareBenchmarks(run_a, run_b) {
		await sleep(180);
		return {
			...benchmarkCompare,
			run_a,
			run_b
		};
	},
	async listCacheEntries(opts) {
		await sleep(160);
		let list = cacheEntries;
		if (opts?.subject) list = list.filter((e) => e.subject === opts.subject);
		if (opts?.stale_only) list = list.filter((e) => e.is_stale);
		return list;
	},
	async getCacheEntry(qid) {
		await sleep(140);
		const entry = getCacheEntryFull(qid);
		if (!entry) throw new Error(`CACHE_ENTRY_NOT_FOUND: ${qid}`);
		return entry;
	},
	async getCacheStatus() {
		await sleep(140);
		return cacheStatus;
	},
	async deleteCacheEntry(qid) {
		await sleep(120);
		return {
			ok: true,
			qid,
			removed: 1
		};
	},
	async deleteCacheModule(module) {
		await sleep(120);
		return {
			ok: true,
			module,
			removed: 0
		};
	},
	async markStale(qid) {
		await sleep(160);
		return {
			ok: true,
			qid,
			marked_stale: true
		};
	},
	async tailLog(name, n = 100) {
		await sleep(120);
		return (logs[name] ?? []).slice(0, n);
	},
	async searchLog(name, query, n = 100) {
		await sleep(120);
		const q = query.toLowerCase();
		return (logs[name] ?? []).filter((entry) => JSON.stringify(entry).toLowerCase().includes(q)).slice(0, n);
	}
};
var BASE = "http://localhost:8000/api/v1";
async function http(path, init) {
	const res = await fetch(`${BASE}${path}`, {
		headers: {
			"Content-Type": "application/json",
			...init?.headers ?? {}
		},
		...init
	});
	if (!res.ok) {
		let detail = res.statusText;
		try {
			const body = await res.json();
			detail = body.detail ?? body.error_code ?? detail;
		} catch {}
		throw new Error(`${res.status} ${detail}`);
	}
	return await res.json();
}
var api = {
	getVersion: () => http("/version"),
	listBooks: () => http("/library/books"),
	addBook: ({ pdf_path, subject, book_title }) => {
		return http(`/library/books?${new URLSearchParams({
			pdf_path,
			subject,
			...book_title ? { book_title } : {}
		})}`, { method: "POST" });
	},
	removeBook: (id) => http(`/library/books/${id}`, { method: "DELETE" }),
	reindexBook: (id) => http(`/library/books/${id}/reindex`, { method: "POST" }),
	getIngestionStatus: (id) => http(`/library/ingestion-status/${id}`),
	listQuestionBanks: () => http("/library/question-banks"),
	listProjects: () => mockApi.listProjects(),
	generate: (req) => http("/questions/generate", {
		method: "POST",
		body: JSON.stringify(req)
	}),
	batchGenerate: (reqs) => http("/questions/batch", {
		method: "POST",
		body: JSON.stringify({ requests: reqs })
	}),
	revise: (qid, req) => http(`/questions/${qid}/revise`, {
		method: "POST",
		body: JSON.stringify(req)
	}),
	listStale: (m, dry = true) => http(`/questions/stale?module_name=${encodeURIComponent(m)}&dry_run=${dry}`),
	inspectPipeline: ({ qid, question_text, subject, marks, question_type = "theory" }) => {
		return http(`/pipeline/inspect?${new URLSearchParams({
			qid,
			question_text,
			subject,
			marks: String(marks),
			question_type
		})}`);
	},
	validate: (b) => http("/validation/validate", {
		method: "POST",
		body: JSON.stringify(b)
	}),
	listBenchmarkRuns: () => http("/benchmarks/runs"),
	getBenchmarkRun: (id) => http(`/benchmarks/runs/${id}`),
	compareBenchmarks: (a, b) => http(`/benchmarks/compare?run_a=${a}&run_b=${b}`),
	listCacheEntries: (opts) => {
		const q = new URLSearchParams();
		if (opts?.subject) q.set("subject", opts.subject);
		if (opts?.stale_only) q.set("stale_only", String(opts.stale_only));
		const qs = q.toString();
		return http(`/cache/entries${qs ? `?${qs}` : ""}`);
	},
	getCacheEntry: (qid) => http(`/cache/entries/${qid}`),
	getCacheStatus: () => http("/cache/status"),
	markStale: (qid) => http("/cache/reanswer", {
		method: "POST",
		body: JSON.stringify({ qid })
	}),
	deleteCacheEntry: (qid, module) => http(`/cache/entries/${encodeURIComponent(qid)}${module ? `?module=${encodeURIComponent(module)}` : ""}`, { method: "DELETE" }),
	deleteCacheModule: (module) => http(`/cache/module/${encodeURIComponent(module)}`, { method: "DELETE" }),
	tailLog: (name, n = 100) => http(`/logs/${name}?n=${n}`),
	searchLog: (name, query, n = 100) => http(`/logs/${name}/search?query=${encodeURIComponent(query)}&n=${n}`),
	uploadBook: async ({ file, subject, title, replace = false }) => {
		const fd = new FormData();
		fd.append("file", file);
		fd.append("subject", subject);
		fd.append("title", title);
		fd.append("replace", String(replace));
		const res = await fetch(`${BASE}/library/books/upload`, {
			method: "POST",
			body: fd
		});
		if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
		return await res.json();
	},
	uploadQuestionBank: async ({ file, name, subject, version = "v1" }) => {
		const fd = new FormData();
		fd.append("file", file);
		fd.append("name", name);
		fd.append("subject", subject);
		fd.append("version", version);
		const res = await fetch(`${BASE}/library/question-banks/upload`, {
			method: "POST",
			body: fd
		});
		if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
		return await res.json();
	},
	getBankQuestions: (name) => http(`/library/question-banks/${encodeURIComponent(name)}/questions`),
	deleteBank: (name) => http(`/library/question-banks/${encodeURIComponent(name)}`, { method: "DELETE" }),
	getJob: (id) => http(`/jobs/${id}`),
	jobPdfUrl: (id) => `${BASE}/jobs/${id}/pdf`,
	solveBank: ({ name, subject, book_id, marks = 10, words_3, words_5, words_10, marks_filter, chapters }) => http("/banks/solve", {
		method: "POST",
		body: JSON.stringify({
			name,
			subject,
			book_id,
			marks,
			words_3,
			words_5,
			words_10,
			marks_filter,
			chapters
		})
	}),
	renderAnswerPdf: async (args) => {
		const res = await fetch(`${BASE}/questions/render-pdf`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(args)
		});
		if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
		return res.blob();
	},
	renderGraphviz: async (dot) => {
		const res = await fetch(`${BASE}/render/graphviz`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ dot })
		});
		if (!res.ok) throw new Error(`${res.status}`);
		return res.blob();
	},
	listProjects: () => mockApi.listProjects()
};
var nav = [
	{
		to: "/",
		label: "Workspace",
		icon: Sparkles,
		kbd: "G"
	},
	{
		to: "/books",
		label: "Books",
		icon: BookOpen,
		section: "Library"
	},
	{
		to: "/question-banks",
		label: "Question Banks",
		icon: Library
	},
	{
		to: "/answers",
		label: "Cached Answers",
		icon: Database,
		section: "Operations"
	},
	{
		to: "/logs",
		label: "Logs",
		icon: ScrollText
	},
	{
		to: "/settings",
		label: "Settings",
		icon: Settings,
		section: "System"
	}
];
function AppSidebar() {
	return /* @__PURE__ */ (0, import_jsx_runtime.jsx)("aside", {
		className: "hidden h-dvh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground md:flex",
		children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(SidebarBody, {})
	});
}
function SidebarBody({ onNavigate }) {
	const pathname = useRouterState({ select: (s) => s.location.pathname });
	const { data: version } = useQuery({
		queryKey: ["version"],
		queryFn: () => api.getVersion(),
		refetchInterval: 3e4,
		retry: false
	});
	const apiBase = "http://localhost:8000/api/v1";
	const apiHost = (() => {
		try {
			return new URL(apiBase).host;
		} catch {
			return apiBase;
		}
	})();
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "flex h-full flex-col",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex h-14 items-center gap-2 px-4",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "grid h-7 w-7 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/30",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("svg", {
						viewBox: "0 0 24 24",
						className: "h-4 w-4",
						fill: "none",
						stroke: "currentColor",
						strokeWidth: "2.2",
						strokeLinecap: "round",
						strokeLinejoin: "round",
						children: [
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("path", { d: "M4 4h6v6H4z" }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("path", { d: "M14 4h6v6h-6z" }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("path", { d: "M4 14h6v6H4z" }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("path", { d: "M14 14h6v6h-6z" })
						]
					})
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "leading-tight",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "text-[13px] font-semibold tracking-tight",
						children: "MedRack"
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "text-[10px] uppercase tracking-[0.14em] text-muted-foreground",
						children: "Authoring"
					})]
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("nav", {
				className: "flex-1 overflow-y-auto px-2 pb-4 pt-2 text-sm",
				children: nav.map((item, i) => {
					const Icon = item.icon;
					const active = pathname === item.to || item.to !== "/" && pathname.startsWith(item.to);
					return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", { children: [item.section && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
						className: "mt-4 px-2 pb-1 text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground/70",
						children: item.section
					}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)(Link, {
						to: item.to,
						onClick: onNavigate,
						"aria-current": active ? "page" : void 0,
						className: cn("group relative flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sidebar-foreground/85 transition-colors", "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground", active && "bg-sidebar-accent text-sidebar-accent-foreground"),
						children: [
							active && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", { className: "absolute inset-y-1 left-0 w-0.5 rounded-r bg-primary" }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Icon, { className: cn("h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground group-hover:text-foreground") }),
							/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
								className: "truncate",
								children: item.label
							}),
							item.kbd && /* @__PURE__ */ (0, import_jsx_runtime.jsx)("kbd", {
								className: "ml-auto hidden rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground group-hover:inline-block",
								children: item.kbd
							})
						]
					})] }, item.to);
				})
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "border-t border-sidebar-border p-3",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
					className: "flex items-center gap-2 rounded-md bg-sidebar-accent/50 px-2.5 py-2",
					children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", { className: cn("h-1.5 w-1.5 rounded-full", version ? "bg-success shadow-[0_0_8px] shadow-success/70" : "bg-warning") }), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
						className: "min-w-0 flex-1 leading-tight",
						children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
							className: "truncate text-[11px] font-medium",
							children: version ? "Backend online" : "Backend offline"
						}), /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
							className: "truncate text-[10px] text-muted-foreground",
							children: [
								apiHost,
								" · v",
								version?.package_version ?? "—"
							]
						})]
					})]
				})
			})
		]
	});
}
function TopBar({ onMenuClick }) {
	const { data: version } = useQuery({
		queryKey: ["version"],
		queryFn: () => api.getVersion()
	});
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("header", {
		className: "flex h-14 shrink-0 items-center gap-2 border-b border-border bg-background/80 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/60 sm:gap-3 sm:px-4",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
				onClick: onMenuClick,
				className: "grid h-9 w-9 shrink-0 place-items-center rounded-md border border-border bg-surface text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground md:hidden",
				"aria-label": "Open navigation menu",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(Menu, { className: "h-5 w-5" })
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
				className: "flex min-w-0 flex-1 items-center gap-2",
				children: /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("button", {
					className: "group inline-flex h-9 w-full max-w-md items-center gap-2 rounded-md border border-border bg-surface px-3 text-left text-sm text-muted-foreground transition-colors hover:border-border hover:bg-surface-2",
					"aria-label": "Open command palette",
					children: [
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Search, { className: "h-3.5 w-3.5 shrink-0" }),
						/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
							className: "truncate",
							children: "Search questions, books, runs…"
						}),
						/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("kbd", {
							className: "ml-auto hidden items-center gap-0.5 rounded border border-border bg-background/60 px-1.5 py-0.5 text-[10px] font-medium sm:flex",
							children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(Command, { className: "h-3 w-3" }), " K"]
						})
					]
				})
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex shrink-0 items-center gap-2 text-xs text-muted-foreground",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("span", {
					className: "hidden rounded-md border border-border bg-surface px-2 py-1 font-mono text-[10px] md:inline-flex",
					children: version ? `v${version.package_version}` : "v—"
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("button", {
					className: "grid h-8 w-8 place-items-center rounded-md border border-border bg-surface text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(CircleQuestionMark, { className: "h-4 w-4" })
				})]
			})
		]
	});
}
function AppShell({ children }) {
	const [navOpen, setNavOpen] = (0, import_react.useState)(false);
	(0, import_react.useEffect)(() => {
		if (!navOpen) return;
		const onKey = (e) => {
			if (e.key === "Escape") setNavOpen(false);
		};
		window.addEventListener("keydown", onKey);
		return () => window.removeEventListener("keydown", onKey);
	}, [navOpen]);
	return /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
		className: "dark flex h-dvh w-full bg-background text-foreground",
		children: [
			/* @__PURE__ */ (0, import_jsx_runtime.jsx)(AppSidebar, {}),
			navOpen && /* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "fixed inset-0 z-50 md:hidden",
				role: "dialog",
				"aria-modal": "true",
				"aria-label": "Navigation menu",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "absolute inset-0 bg-black/60 backdrop-blur-sm",
					onClick: () => setNavOpen(false)
				}), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("div", {
					className: "absolute inset-y-0 left-0 w-64 max-w-[82%] border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-2xl",
					children: /* @__PURE__ */ (0, import_jsx_runtime.jsx)(SidebarBody, { onNavigate: () => setNavOpen(false) })
				})]
			}),
			/* @__PURE__ */ (0, import_jsx_runtime.jsxs)("div", {
				className: "flex min-w-0 flex-1 flex-col",
				children: [/* @__PURE__ */ (0, import_jsx_runtime.jsx)(TopBar, { onMenuClick: () => setNavOpen(true) }), /* @__PURE__ */ (0, import_jsx_runtime.jsx)("main", {
					"aria-label": "Main content",
					className: "min-h-0 flex-1 overflow-auto",
					children
				})]
			})
		]
	});
}
//#endregion
export { api as n, cn as r, AppShell as t };
