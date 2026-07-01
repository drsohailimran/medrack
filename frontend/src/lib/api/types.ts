// MedRack API types — sourced verbatim from docs/frontend/DATA_MODELS.md.
// These types form the single contract between the frontend and the backend.

// Subject is dynamic — derived from imported books at runtime. We keep a
// closed set here only for the canonical "main" subjects; the Workspace
// segment control accepts any string and lists the subject of every
// indexed book.
export const KNOWN_SUBJECTS = [
  { value: "psm", label: "PSM" },
  { value: "fmt", label: "FMT" },
  { value: "medicine", label: "Medicine" },
  { value: "surgery", label: "Surgery" },
  { value: "obgyn", label: "OBGYN" },
  { value: "pediatrics", label: "Pediatrics" },
  { value: "ortho", label: "Ortho" },
  { value: "ent", label: "ENT" },
  { value: "ophthalmology", label: "Ophth" },
  { value: "anesthesia", label: "Anesth" },
] as const;

export type Subject = string;
export type Marks = 5 | 10 | 15;
export type QuestionType = "theory" | "mcq";
export type IngestionStatusValue = "unknown" | "pending" | "running" | "succeeded" | "failed";

export interface ErrorResponse {
  error_code: string;
  detail: string;
}

export interface BookInfo {
  schema_version: 1;
  book_id: string;
  title: string;
  subject: Subject | "unknown";
  path: string;
  indexed: boolean;
  indexed_at: string | null;
  chunk_count: number;
}

export interface QuestionBankInfo {
  schema_version: 1;
  name: string;
  version: string;
  subject: Subject;
  path: string;
  question_count: number;
}

// A single question surfaced from a bank's cached entries. Derived on the
// frontend from CacheEntry rows whose qid is namespaced `<bank>::<qid>`.
export interface BankQuestionInfo {
  qid: string;
  subject: Subject;
  target_word_count: number;
}

// A real question stored inside a question bank (from the backend bank JSON).
export interface BankQuestion {
  qid: string;
  question_text: string;
  marks?: number;
  type?: string;
  section?: string;
  topic?: string;
  subject?: string;
}

export interface BankQuestionsResponse {
  name: string;
  subject: Subject;
  version: string;
  questions: BankQuestion[];
}

export interface IngestionStatus {
  schema_version: 1;
  book_id: string;
  status: IngestionStatusValue;
  started_at: string;
  finished_at: string | null;
  chunk_count: number;
  error: string | null;
}

export interface GenerateRequest {
  qid: string;
  question_text: string;
  subject: Subject;
  marks: Marks;
  question_type?: QuestionType;
  book_id?: string;
  chapter?: string;
  // Explicit answer length in words (overrides the marks default).
  word_count_target?: number;
}

export interface GenerationResult {
  schema_version: 1;
  qid: string;
  ok: boolean;
  answer_text: string | null;
  pdf_path: string | null;
  cache_hit: boolean;
  error: string | null;
  token_count: number;
  latency_seconds: number;
}

export interface BatchGenerateRequest {
  requests: GenerateRequest[];
}

export interface ReviseRequest {
  subject: Subject;
  revised_question_text: string;
}

export interface StaleResponse {
  ok: boolean;
  dry_run: boolean;
  stale_count?: number;
  stale_qids?: string[];
  reanswered_count?: number;
  results?: GenerationResult[];
}

export type PipelineStageName =
  "planner" | "blueprint" | "retrieval" | "reranker" | "writer" | "validator";

export interface PipelineStageOutput {
  schema_version: 1;
  stage: PipelineStageName;
  output: Record<string, unknown>;
  latency_seconds: number;
}

export interface PipelineTrace {
  schema_version: 1;
  qid: string;
  stages: PipelineStageOutput[];
  total_latency_seconds: number;
}

export type Severity = "pass" | "warn" | "fail";

export interface ValidationResult {
  rule_name: string;
  severity: Severity;
  message: string;
  details: Record<string, unknown> | null;
}

export interface ValidationReport {
  schema_version: 1;
  pass: boolean;
  score: number;
  results: ValidationResult[];
  failed_rules: string[];
  warnings: string[];
  informational_messages: string[];
}

export interface BenchmarkSummary {
  schema_version: 1;
  run_id: string;
  timestamp: string;
  llm_mode: "mock" | "real";
  n_questions: number;
  n_success: number;
  n_failure: number;
  cache_hit_rate: number;
  total_tokens: number;
  avg_total_latency_seconds: number;
  avg_pdf_generation_seconds: number;
  json_report_path: string;
  markdown_report_path: string | null;
}

export interface BenchmarkCompareResponse {
  ok: boolean;
  run_a: string;
  run_b: string;
  delta: {
    n_questions: number;
    n_success: number;
    n_failure: number;
    cache_hit_rate: number;
    total_tokens: number;
    avg_total_latency_seconds: number;
  };
  error?: string;
}

export interface CacheEntry {
  schema_version: 1;
  qid: string;
  subject: Subject;
  is_stale: boolean;
  stale_reasons: string[];
  versions: {
    schema: number;
    prompt: number;
    retrieval: number;
    planner: number;
    validator: number;
    reranker: number;
    renderer: number;
    embedding_model: string;
  };
  target_word_count: number;
  cached_at: string | null;
  last_validated_at: string | null;
  validation_score: number | null;
  // The module the answer belongs to (a bank's safe stem for bank answers,
  // or a book_id / "<subject>-default" for single generations) + the question.
  module?: string;
  question_text?: string;
}

export interface CacheEntryFull extends CacheEntry {
  module: string;
  chapter: string;
  question_text: string;
  answer_text: string;
  pdf_path: string;
  stale: boolean;
  embedding_model: string;
  package_version: string;
}

export interface CacheStatus {
  schema_version: 1;
  total_entries: number;
  by_subject: Record<string, number>;
  stale_by_subject: Record<string, number>;
}

export interface VersionInfo {
  schema_version: 1;
  package_version: string;
  pipeline_versions: {
    schema: number;
    prompt: number;
    retrieval: number;
    planner: number;
    validator: number;
    reranker: number;
    renderer: number;
  };
  benchmark_baseline_tag: string | null;
}

export type LogName = "ingestion" | "generation" | "validation" | "benchmark";
export type LogEntry = Record<string, unknown>;

// --- Async jobs (book ingest, question-bank extract, solve bank) ---
export type JobStatusValue = "pending" | "running" | "done" | "error";

export interface JobStatus {
  schema_version: 1;
  job_id: string;
  kind: string;
  status: JobStatusValue;
  percent: number; // 0..100, two-decimal precision
  message: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

// The immediate response when starting an async job.
export interface JobHandle {
  job_id: string;
  kind: string;
  book_title?: string;
}

// Frontend-only "Project" abstraction (per DATA_MODELS.md).
export interface Project {
  id: string;
  name: string;
  subject: Subject;
  description: string;
  question_count: number;
  created_at: string;
  updated_at: string;
}
