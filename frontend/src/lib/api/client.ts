// MedRack API client.
//
// Two implementations live behind a single shared interface:
//   - `httpApi`  — calls the real backend at VITE_MEDRACK_API_BASE
//                  (default http://localhost:8000/api/v1). One method per
//                  endpoint in docs/frontend/API_REFERENCE.md.
//   - `mockApi`  — returns deterministic fixtures from ./mock-data with a
//                  small artificial latency so loading states are visible.
//
// Components MUST import the named `api` export below; swapping
// implementations is a one-line change here when the backend is wired up.

import * as mock from "./mock-data";
import type {
  BankQuestionsResponse,
  BenchmarkCompareResponse,
  BenchmarkSummary,
  BookInfo,
  CacheEntry,
  CacheEntryFull,
  CacheStatus,
  GenerateRequest,
  GenerationResult,
  IngestionStatus,
  JobHandle,
  JobStatus,
  LogEntry,
  LogName,
  PipelineTrace,
  Project,
  QuestionBankInfo,
  ReviseRequest,
  StaleResponse,
  Subject,
  ValidationReport,
  VersionInfo,
  LlmStatus,
} from "./types";

export interface MedRackApi {
  // Version / health
  getVersion(): Promise<VersionInfo>;
  /** P3: live LLM indicator (model + endpoint + online). */
  getLlmStatus(): Promise<LlmStatus>;

  // Library
  listBooks(): Promise<BookInfo[]>;
  addBook(args: {
    pdf_path: string;
    subject: Subject;
    book_title?: string;
  }): Promise<{ ok: true; book_id: string; path: string; subject: Subject }>;
  removeBook(
    book_id: string,
  ): Promise<{ ok: boolean; book_id: string; moved_to?: string; error?: string }>;
  reindexBook(book_id: string): Promise<{ ok: true; book_id: string }>;
  getIngestionStatus(book_id: string): Promise<IngestionStatus>;
  listQuestionBanks(): Promise<QuestionBankInfo[]>;
  // Upload a book PDF and ingest it into the KB. Returns a job to poll.
  uploadBook(args: {
    file: File;
    subject: Subject;
    title: string;
    replace?: boolean;
    /** P1: Windows hybrid OCR (stop model → RapidOCR → clean PDF → reindex) */
    hybrid_ocr?: boolean;
    /** Optional Marker table pass (slower; needs GPU free after model stop) */
    use_marker?: boolean;
  }): Promise<JobHandle>;
  // Upload a question-bank PDF. Extraction is async; returns a job to poll.
  uploadQuestionBank(args: {
    file: File;
    name: string;
    subject: Subject;
    version?: string;
  }): Promise<JobHandle>;
  // View the questions inside a bank.
  getBankQuestions(name: string): Promise<BankQuestionsResponse>;
  // Delete a question bank.
  deleteBank(name: string): Promise<{ ok: boolean; name: string; error?: string }>;

  // Jobs (async progress for ingest / extract / solve)
  getJob(job_id: string): Promise<JobStatus>;
  /** P3: cooperative cancel — stops after the current question. */
  cancelJob(job_id: string): Promise<{
    ok: boolean;
    job_id: string;
    status: string;
    cancel_requested: boolean;
    message?: string;
  }>;
  jobPdfUrl(job_id: string): string;

  // Solve a whole question bank into one PDF (the "approve" action).
  // words_5 / words_10 set the answer length per marks tier.
  solveBank(args: {
    name: string;
    subject: Subject;
    book_id?: string;
    marks?: number;
    words_3?: number;
    words_5?: number;
    words_10?: number;
    marks_filter?: number[];
    chapters?: string[];
  }): Promise<JobHandle>;
  // Render a single answer to a real PDF (returns the PDF blob).
  renderAnswerPdf(args: {
    qid: string;
    subject: Subject;
    question_text: string;
    answer_text: string;
    marks: number;
    question_type?: string;
  }): Promise<Blob>;
  // Render a Graphviz DOT flowchart to a PNG (returns the image blob).
  renderGraphviz(dot: string): Promise<Blob>;

  // Projects (frontend-only abstraction)
  listProjects(): Promise<Project[]>;

  // Generation
  generate(req: GenerateRequest): Promise<GenerationResult>;
  batchGenerate(reqs: GenerateRequest[]): Promise<GenerationResult[]>;
  revise(qid: string, req: ReviseRequest): Promise<GenerationResult>;
  listStale(module_name: string, dry_run?: boolean): Promise<StaleResponse>;

  // Pipeline
  inspectPipeline(args: {
    qid: string;
    question_text: string;
    subject: Subject;
    marks: number;
    question_type?: string;
  }): Promise<PipelineTrace>;

  // Validation
  validate(args: {
    answer: string;
    blueprint?: object | null;
    disabled_rules?: string[];
  }): Promise<ValidationReport>;

  // Benchmarks
  listBenchmarkRuns(): Promise<BenchmarkSummary[]>;
  getBenchmarkRun(run_id: string): Promise<BenchmarkSummary>;
  compareBenchmarks(run_a: string, run_b: string): Promise<BenchmarkCompareResponse>;

  // Cache
  listCacheEntries(opts?: { subject?: Subject; stale_only?: boolean }): Promise<CacheEntry[]>;
  getCacheEntry(qid: string): Promise<CacheEntryFull>;
  getCacheStatus(): Promise<CacheStatus>;
  markStale(
    qid: string,
  ): Promise<{ ok: boolean; qid: string; marked_stale?: boolean; error?: string }>;
  // Delete a cached answer (scoped to its module/bank), or all for a module.
  deleteCacheEntry(
    qid: string,
    module?: string,
  ): Promise<{ ok: boolean; qid: string; removed?: number }>;
  deleteCacheModule(module: string): Promise<{ ok: boolean; module: string; removed?: number }>;

  // Logs
  tailLog(name: LogName, n?: number): Promise<LogEntry[]>;
  searchLog(name: LogName, query: string, n?: number): Promise<LogEntry[]>;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function jitter(min: number, max: number) {
  return min + Math.random() * (max - min);
}

export const mockApi: MedRackApi = {
  async getVersion() {
    await sleep(120);
    return mock.versionInfo;
  },
  async getLlmStatus() {
    await sleep(80);
    return {
      schema_version: 1 as const,
      mode: "mock",
      provider: "mock",
      model: "mock",
      base_url: "",
      online: true,
      detail: "mock client",
      latency_ms: 1,
    };
  },

  async listBooks() {
    await sleep(jitter(140, 260));
    return mock.books;
  },
  async addBook({ subject, book_title }) {
    if (subject !== "psm" && subject !== "fmt") throw new Error("Subject must be psm or fmt");
    await sleep(400);
    const book_id = (book_title ?? "new_book").toLowerCase().replace(/\s+/g, "_");
    return {
      ok: true as const,
      book_id,
      path: `/home/user/.medrack/inbox/${book_id}.pdf`,
      subject,
    };
  },
  async removeBook(book_id) {
    await sleep(200);
    return { ok: true as const, book_id, moved_to: "/home/user/.medrack/trash" };
  },
  async reindexBook(book_id) {
    await sleep(200);
    return { ok: true as const, book_id };
  },
  async getIngestionStatus(book_id) {
    await sleep(200);
    return (
      mock.ingestionStatuses[book_id] ?? {
        schema_version: 1,
        book_id,
        status: "unknown",
        started_at: new Date().toISOString(),
        finished_at: null,
        chunk_count: 0,
        error: null,
      }
    );
  },
  async listQuestionBanks() {
    await sleep(180);
    return mock.questionBanks;
  },
  async uploadBook({ title }) {
    await sleep(200);
    return { job_id: `mock-ingest-${Date.now()}`, kind: "ingest_book", book_title: title };
  },
  async uploadQuestionBank({ name }) {
    await sleep(200);
    return { job_id: `mock-extract-${Date.now()}`, kind: "extract_bank", book_title: name };
  },
  async getBankQuestions(name) {
    await sleep(120);
    return { name, subject: "psm", version: "v1", questions: [] };
  },
  async deleteBank(name) {
    await sleep(120);
    return { ok: true, name };
  },
  async cancelJob(job_id) {
    await sleep(80);
    return {
      ok: true,
      job_id,
      status: "cancelled",
      cancel_requested: true,
      message: "Mock cancel",
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
      result: { question_count: 20, answered: 20, download_name: "mock.pdf" },
      error: null,
    };
  },
  jobPdfUrl(job_id) {
    return `mock://jobs/${job_id}/pdf`;
  },
  async solveBank({ name }) {
    await sleep(200);
    return { job_id: `mock-solve-${Date.now()}`, kind: "solve_bank", book_title: name };
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
    return mock.projects;
  },

  async generate(req) {
    // Mock: 5s of latency for "real" feel, 200ms if "cache hit" qid.
    const cacheHit = req.qid === "q001" || req.qid === "q014";
    await sleep(cacheHit ? 250 : 2400);
    return {
      ...mock.generationResultSuccess,
      qid: req.qid,
      cache_hit: cacheHit,
      latency_seconds: cacheHit ? 0.18 : jitter(4.2, 7.8),
      token_count: cacheHit ? 0 : Math.round(jitter(900, 1600)),
    };
  },
  async batchGenerate(reqs) {
    const out: GenerationResult[] = [];
    for (const r of reqs) out.push(await mockApi.generate(r));
    return out;
  },
  async revise(qid, req) {
    await sleep(2200);
    return { ...mock.generationResultSuccess, qid, cache_hit: false };
  },
  async listStale(_module, dry_run = true) {
    await sleep(180);
    const stale = mock.cacheEntries.filter((e) => e.is_stale).map((e) => e.qid);
    return dry_run
      ? { ok: true, dry_run: true, stale_count: stale.length, stale_qids: stale }
      : { ok: true, dry_run: false, reanswered_count: stale.length, results: [] };
  },

  async inspectPipeline({ qid }) {
    await sleep(360);
    return { ...mock.pipelineTrace, qid };
  },

  async validate() {
    await sleep(220);
    return mock.validationReportPass;
  },

  async listBenchmarkRuns() {
    await sleep(200);
    return mock.benchmarkRuns;
  },
  async getBenchmarkRun(run_id) {
    const run = mock.benchmarkRuns.find((r) => r.run_id === run_id);
    if (!run) throw new Error(`RUN_NOT_FOUND: ${run_id}`);
    await sleep(160);
    return run;
  },
  async compareBenchmarks(run_a, run_b) {
    await sleep(180);
    return { ...mock.benchmarkCompare, run_a, run_b };
  },

  async listCacheEntries(opts) {
    await sleep(160);
    let list = mock.cacheEntries;
    if (opts?.subject) list = list.filter((e) => e.subject === opts.subject);
    if (opts?.stale_only) list = list.filter((e) => e.is_stale);
    return list;
  },
  async getCacheEntry(qid) {
    await sleep(140);
    const entry = mock.getCacheEntryFull(qid);
    if (!entry) throw new Error(`CACHE_ENTRY_NOT_FOUND: ${qid}`);
    return entry;
  },
  async getCacheStatus() {
    await sleep(140);
    return mock.cacheStatus;
  },
  async deleteCacheEntry(qid) {
    await sleep(120);
    return { ok: true, qid, removed: 1 };
  },
  async deleteCacheModule(module) {
    await sleep(120);
    return { ok: true, module, removed: 0 };
  },
  async markStale(qid) {
    await sleep(160);
    return { ok: true as const, qid, marked_stale: true as const };
  },

  async tailLog(name, n = 100) {
    await sleep(120);
    return (mock.logs[name] ?? []).slice(0, n);
  },
  async searchLog(name, query, n = 100) {
    await sleep(120);
    const q = query.toLowerCase();
    return (mock.logs[name] ?? [])
      .filter((entry) => JSON.stringify(entry).toLowerCase().includes(q))
      .slice(0, n);
  },
};

// --- HTTP implementation (kept thin; not used in dev). ----------------------

const BASE =
  (import.meta.env.VITE_MEDRACK_API_BASE as string | undefined) ?? "http://localhost:8000/api/v1";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body.error_code ?? detail;
    } catch {
      // Body is not JSON or unreadable; fall through to statusText.
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return (await res.json()) as T;
}

export const httpApi: MedRackApi = {
  getVersion: () => http("/version"),
  getLlmStatus: () => http("/llm/status"),
  listBooks: () => http("/library/books"),
  addBook: ({ pdf_path, subject, book_title }) => {
    const q = new URLSearchParams({ pdf_path, subject, ...(book_title ? { book_title } : {}) });
    return http(`/library/books?${q}`, { method: "POST" });
  },
  removeBook: (id) => http(`/library/books/${id}`, { method: "DELETE" }),
  reindexBook: (id) => http(`/library/books/${id}/reindex`, { method: "POST" }),
  getIngestionStatus: (id) => http(`/library/ingestion-status/${id}`),
  listQuestionBanks: () => http("/library/question-banks"),
  // Projects are frontend-only — no HTTP endpoint exists. Reuse mock data.
  listProjects: () => mockApi.listProjects(),
  generate: (req) => http("/questions/generate", { method: "POST", body: JSON.stringify(req) }),
  batchGenerate: (reqs) =>
    http("/questions/batch", { method: "POST", body: JSON.stringify({ requests: reqs }) }),
  revise: (qid, req) =>
    http(`/questions/${qid}/revise`, { method: "POST", body: JSON.stringify(req) }),
  listStale: (m, dry = true) =>
    http(`/questions/stale?module_name=${encodeURIComponent(m)}&dry_run=${dry}`),
  inspectPipeline: ({ qid, question_text, subject, marks, question_type = "theory" }) => {
    const q = new URLSearchParams({
      qid,
      question_text,
      subject,
      marks: String(marks),
      question_type,
    });
    return http(`/pipeline/inspect?${q}`);
  },
  validate: (b) => http("/validation/validate", { method: "POST", body: JSON.stringify(b) }),
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
  markStale: (qid) => http("/cache/reanswer", { method: "POST", body: JSON.stringify({ qid }) }),
  deleteCacheEntry: (qid, module) =>
    http(
      `/cache/entries/${encodeURIComponent(qid)}${module ? `?module=${encodeURIComponent(module)}` : ""}`,
      { method: "DELETE" },
    ),
  deleteCacheModule: (module) =>
    http(`/cache/module/${encodeURIComponent(module)}`, { method: "DELETE" }),
  tailLog: (name, n = 100) => http(`/logs/${name}?n=${n}`),
  searchLog: (name, query, n = 100) =>
    http(`/logs/${name}/search?query=${encodeURIComponent(query)}&n=${n}`),
  uploadBook: async ({
    file,
    subject,
    title,
    replace = false,
    hybrid_ocr = false,
    use_marker = false,
  }) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("subject", subject);
    fd.append("title", title);
    fd.append("replace", String(replace));
    fd.append("hybrid_ocr", String(hybrid_ocr));
    fd.append("use_marker", String(use_marker));
    const res = await fetch(`${BASE}/library/books/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
    return (await res.json()) as JobHandle;
  },
  uploadQuestionBank: async ({ file, name, subject, version = "v1" }) => {
    // multipart/form-data (File + fields), so use raw fetch not `http`.
    const fd = new FormData();
    fd.append("file", file);
    fd.append("name", name);
    fd.append("subject", subject);
    fd.append("version", version);
    const res = await fetch(`${BASE}/library/question-banks/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
    return (await res.json()) as JobHandle;
  },
  getBankQuestions: (name) => http(`/library/question-banks/${encodeURIComponent(name)}/questions`),
  deleteBank: (name) =>
    http(`/library/question-banks/${encodeURIComponent(name)}`, { method: "DELETE" }),
  getJob: (id) => http(`/jobs/${id}`),
  cancelJob: (id) => http(`/jobs/${id}/cancel`, { method: "POST" }),
  jobPdfUrl: (id) => `${BASE}/jobs/${id}/pdf`,
  solveBank: ({ name, subject, book_id, marks = 10, words_3, words_5, words_10, marks_filter, chapters }) =>
    http("/banks/solve", {
      method: "POST",
      body: JSON.stringify({
        name, subject, book_id, marks, words_3, words_5, words_10, marks_filter, chapters,
      }),
    }),
  renderAnswerPdf: async (args) => {
    const res = await fetch(`${BASE}/questions/render-pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
    return res.blob();
  },
  renderGraphviz: async (dot) => {
    const res = await fetch(`${BASE}/render/graphviz`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dot }),
    });
    if (!res.ok) throw new Error(`${res.status}`);
    return res.blob();
  },
};

// One-line toggle: swap mockApi for httpApi to wire up the real
// backend. Components import `api`; the implementation is hidden
// behind the `MedRackApi` interface. `listProjects` has no backend
// endpoint (per the Frontend Handoff Package v1.0: projects are a
// frontend-only abstraction), so we keep it on the mock.
const httpApiWithMockProjects: MedRackApi = {
  ...httpApi,
  listProjects: () => mockApi.listProjects(),
};
export const api: MedRackApi = httpApiWithMockProjects;
