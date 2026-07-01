// Mock data fixtures for MedRack. Shapes mirror docs/frontend/MOCK_DATA.json.
// In production these are replaced by the real /api/v1/* responses; only the
// `mockApi` implementation in ./client.ts should reference this file.

import type {
  BenchmarkCompareResponse,
  BenchmarkSummary,
  BookInfo,
  CacheEntry,
  CacheEntryFull,
  CacheStatus,
  GenerationResult,
  IngestionStatus,
  LogEntry,
  LogName,
  PipelineTrace,
  Project,
  QuestionBankInfo,
  ValidationReport,
  VersionInfo,
} from "./types";

export const versionInfo: VersionInfo = {
  schema_version: 1,
  package_version: "0.3.0-backend-freeze",
  pipeline_versions: {
    schema: 2,
    prompt: 1,
    retrieval: 1,
    planner: 0,
    validator: 0,
    reranker: 0,
    renderer: 1,
  },
  benchmark_baseline_tag: "phase-5-baseline",
};

export const books: BookInfo[] = [
  {
    schema_version: 1,
    book_id: "park_psm_v4",
    title: "Park's Textbook of Preventive and Social Medicine",
    subject: "psm",
    path: "/home/user/.medrack/inbox/park_psm_v4.pdf",
    indexed: true,
    indexed_at: "2025-01-15T10:30:00",
    chunk_count: 1234,
  },
  {
    schema_version: 1,
    book_id: "park_fmt_v3",
    title: "Park's Textbook of Forensic Medicine & Toxicology",
    subject: "fmt",
    path: "/home/user/.medrack/inbox/park_fmt_v3.pdf",
    indexed: true,
    indexed_at: "2025-01-20T14:15:00",
    chunk_count: 876,
  },
  {
    schema_version: 1,
    book_id: "kpark_clinical",
    title: "K. Park Clinical PSM Companion",
    subject: "psm",
    path: "/home/user/.medrack/inbox/kpark_clinical.pdf",
    indexed: false,
    indexed_at: null,
    chunk_count: 0,
  },
  {
    schema_version: 1,
    book_id: "reddy_fmt",
    title: "Essentials of Forensic Medicine — Reddy",
    subject: "fmt",
    path: "/home/user/.medrack/inbox/reddy_fmt.pdf",
    indexed: true,
    indexed_at: "2025-02-02T09:12:00",
    chunk_count: 642,
  },
];

export const questionBanks: QuestionBankInfo[] = [
  {
    schema_version: 1,
    name: "PSM Regression v1",
    version: "v1",
    subject: "psm",
    path: "/home/user/.medrack/tests/regression_datasets/v1.json",
    question_count: 20,
  },
  {
    schema_version: 1,
    name: "FMT Regression v1",
    version: "v1",
    subject: "fmt",
    path: "/home/user/.medrack/tests/regression_datasets/fmt_v1.json",
    question_count: 12,
  },
  {
    schema_version: 1,
    name: "NEET PG Mock 2024",
    version: "2024-01",
    subject: "psm",
    path: "/home/user/.medrack/tests/regression_datasets/neet_pg_2024.json",
    question_count: 45,
  },
];

export const projects: Project[] = [
  {
    id: "prj-neet-pg-2026",
    name: "NEET PG 2026 Prep",
    subject: "psm",
    description: "Long-answer practice across PSM modules 1–8.",
    question_count: 42,
    created_at: "2025-12-01T08:00:00",
    updated_at: "2026-06-20T11:32:00",
  },
  {
    id: "prj-university-finals",
    name: "University Finals — FMT",
    subject: "fmt",
    description: "10-mark and 5-mark essays covering toxicology and forensic pathology.",
    question_count: 18,
    created_at: "2026-02-10T14:00:00",
    updated_at: "2026-06-15T09:11:00",
  },
];

export const ingestionStatuses: Record<string, IngestionStatus> = {
  park_psm_v4: {
    schema_version: 1,
    book_id: "park_psm_v4",
    status: "succeeded",
    started_at: "2025-01-15T10:25:00",
    finished_at: "2025-01-15T10:30:00",
    chunk_count: 1234,
    error: null,
  },
  kpark_clinical: {
    schema_version: 1,
    book_id: "kpark_clinical",
    status: "running",
    started_at: "2026-06-29T09:00:00",
    finished_at: null,
    chunk_count: 0,
    error: null,
  },
};

export const sampleAnswer = `Introduction: Diabetes mellitus is a chronic metabolic disorder characterized by sustained hyperglycemia resulting from defects in insulin secretion, insulin action, or both. It represents one of the leading non-communicable disease burdens of the 21st century, with India bearing a disproportionate share of cases.

Definition: According to the World Health Organization, diabetes mellitus is a group of metabolic diseases defined by chronically elevated blood glucose. Diagnostic thresholds include fasting plasma glucose ≥ 126 mg/dL, 2-hour plasma glucose ≥ 200 mg/dL on OGTT, or HbA1c ≥ 6.5%. [chunk_park_dm_001]

Epidemiology: The global prevalence of diabetes rose from 108 million in 1980 to over 537 million in 2021. India hosts an estimated 77 million adults with diabetes — second only to China — with projections reaching 134 million by 2045. Type 2 diabetes accounts for 90–95% of all cases; urban prevalence (11.2%) exceeds rural prevalence (5.2%). [chunk_park_dm_004]

Etiology: Type 2 diabetes is driven by insulin resistance compounded by progressive beta-cell dysfunction. Key risk factors include obesity (especially central adiposity), physical inactivity, family history, increasing age, gestational diabetes, and ethnicity. [chunk_park_dm_007]

Management: Management rests on four pillars — lifestyle modification, pharmacotherapy, monitoring, and prevention of complications.

1. Lifestyle modification: medical nutrition therapy, ≥150 minutes/week moderate aerobic activity, weight reduction of 5–10%, smoking cessation.
2. Pharmacotherapy: First-line is metformin 500 mg twice daily, titrated to 2 g/day. Add SGLT2 inhibitors or GLP-1 agonists for patients with cardiovascular or renal risk. Insulin is reserved for severe hyperglycemia or when oral agents fail. [chunk_park_dm_011]
3. Monitoring: HbA1c every 3 months until target (<7%) is achieved, then biannually. Annual eye, foot, and renal screening.
4. Prevention of complications: blood pressure <130/80 mmHg, LDL <70 mg/dL, ACE inhibitor or ARB for proteinuria. [chunk_park_dm_015]

Conclusion: Diabetes mellitus requires lifelong, multi-disciplinary management. Early diagnosis, sustained lifestyle change, evidence-based pharmacotherapy, and structured screening for complications remain the cornerstones of reducing morbidity and mortality.`;

export const generationResultSuccess: GenerationResult = {
  schema_version: 1,
  qid: "q001",
  ok: true,
  answer_text: sampleAnswer,
  pdf_path: "/home/user/.medrack/cache/psm-module-1/diabetes/q001.pdf",
  cache_hit: false,
  error: null,
  token_count: 1234,
  latency_seconds: 5.6,
};

export const pipelineTrace: PipelineTrace = {
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
          { name: "introduction", target_word_count: 116, required: true, category: "framing" },
          {
            name: "definition",
            target_word_count: 150,
            required: true,
            category: "medical",
            metadata_section: "section_definition",
          },
          {
            name: "epidemiology",
            target_word_count: 150,
            required: true,
            category: "medical",
            metadata_section: "section_epidemiology",
          },
          {
            name: "management",
            target_word_count: 290,
            required: true,
            category: "medical",
            metadata_section: "section_management",
          },
          { name: "conclusion", target_word_count: 78, required: true, category: "framing" },
        ],
        required_metadata_categories: [
          "section_definition",
          "section_epidemiology",
          "section_management",
        ],
      },
      latency_seconds: 0.001,
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
            evidence_category: "framing",
          },
          {
            section_name: "definition",
            priority: 0,
            min_chunks: 1,
            max_chunks: 3,
            evidence_category: "medical",
            metadata_filter: { section_definition: true },
          },
          {
            section_name: "epidemiology",
            priority: 0,
            min_chunks: 1,
            max_chunks: 3,
            evidence_category: "medical",
            metadata_filter: { section_epidemiology: true },
          },
          {
            section_name: "management",
            priority: 0,
            min_chunks: 1,
            max_chunks: 3,
            evidence_category: "medical",
            metadata_filter: { section_management: true },
          },
          {
            section_name: "conclusion",
            priority: 0,
            min_chunks: 1,
            max_chunks: 3,
            evidence_category: "framing",
          },
        ],
        aggregate_metadata_filter: {
          $or: [
            { section_definition: true },
            { section_epidemiology: true },
            { section_management: true },
          ],
        },
        evidence_categories: ["framing", "medical"],
      },
      latency_seconds: 0.001,
    },
    {
      schema_version: 1,
      stage: "retrieval",
      output: { strategy: "AdaptiveStrategy", top_k_by_marks: { "5": 5, "10": 8, "15": 10 } },
      latency_seconds: 0.012,
    },
    {
      schema_version: 1,
      stage: "reranker",
      output: {
        metadata_reranker: "MetadataBoostReranker",
        semantic_reranker_options: ["IdentityReranker", "HeuristicReranker"],
        default_semantic_reranker: "IdentityReranker",
      },
      latency_seconds: 0.003,
    },
    {
      schema_version: 1,
      stage: "writer",
      output: { theory_long_target_words: 775, theory_short_target_words: 475 },
      latency_seconds: 4.32,
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
          "ReferenceConsistencyRule",
        ],
      },
      latency_seconds: 0.008,
    },
  ],
  total_latency_seconds: 4.356,
};

export const validationReportPass: ValidationReport = {
  schema_version: 1,
  pass: true,
  score: 0.94,
  results: [
    { rule_name: "FormattingRule", severity: "pass", message: "Formatting OK", details: null },
    {
      rule_name: "HeadingStructureRule",
      severity: "pass",
      message: "Found 6 section heading(s)",
      details: null,
    },
    {
      rule_name: "DuplicateSectionRule",
      severity: "pass",
      message: "No duplicate sections",
      details: null,
    },
    {
      rule_name: "EmptySectionRule",
      severity: "pass",
      message: "No empty sections",
      details: null,
    },
    {
      rule_name: "WordCountRule",
      severity: "warn",
      message: "1 section close to upper bound",
      details: { offending: [{ section: "management", target: 290, actual: 316 }] },
    },
    {
      rule_name: "RequiredSectionsRule",
      severity: "pass",
      message: "All 5 required section(s) present",
      details: null,
    },
    {
      rule_name: "BlueprintComplianceRule",
      severity: "pass",
      message: "All blueprint sections present",
      details: null,
    },
    {
      rule_name: "EvidenceCoverageRule",
      severity: "pass",
      message: "Found references in 5/5 medical section(s)",
      details: null,
    },
    {
      rule_name: "ReferenceConsistencyRule",
      severity: "pass",
      message: "All chunk references are unique within sections",
      details: null,
    },
  ],
  failed_rules: [],
  warnings: ["WordCountRule"],
  informational_messages: [
    "[FormattingRule] Formatting OK",
    "[HeadingStructureRule] Found 6 section heading(s)",
    "[EvidenceCoverageRule] Found references in 5/5 medical section(s)",
  ],
};

export const benchmarkRuns: BenchmarkSummary[] = [
  {
    schema_version: 1,
    run_id: "20260628T193408Z",
    timestamp: "2026-06-28T19:34:08Z",
    llm_mode: "real",
    n_questions: 20,
    n_success: 40,
    n_failure: 0,
    cache_hit_rate: 0.55,
    total_tokens: 18420,
    avg_total_latency_seconds: 6.34,
    avg_pdf_generation_seconds: 0.121,
    json_report_path: "/home/user/.medrack/benchmarks/runs/20260628T193408Z_run.json",
    markdown_report_path: "/home/user/.medrack/benchmarks/runs/20260628T193408Z_report.md",
  },
  {
    schema_version: 1,
    run_id: "20260627T100000Z",
    timestamp: "2026-06-27T10:00:00Z",
    llm_mode: "real",
    n_questions: 20,
    n_success: 39,
    n_failure: 1,
    cache_hit_rate: 0.4,
    total_tokens: 21100,
    avg_total_latency_seconds: 7.21,
    avg_pdf_generation_seconds: 0.118,
    json_report_path: "/home/user/.medrack/benchmarks/runs/20260627T100000Z_run.json",
    markdown_report_path: "/home/user/.medrack/benchmarks/runs/20260627T100000Z_report.md",
  },
  {
    schema_version: 1,
    run_id: "20260620T084500Z",
    timestamp: "2026-06-20T08:45:00Z",
    llm_mode: "mock",
    n_questions: 20,
    n_success: 40,
    n_failure: 0,
    cache_hit_rate: 0.5,
    total_tokens: 12000,
    avg_total_latency_seconds: 0.169,
    avg_pdf_generation_seconds: 0.005,
    json_report_path: "/home/user/.medrack/benchmarks/runs/20260620T084500Z_run.json",
    markdown_report_path: null,
  },
];

export const benchmarkCompare: BenchmarkCompareResponse = {
  ok: true,
  run_a: "20260627T100000Z",
  run_b: "20260628T193408Z",
  delta: {
    n_questions: 0,
    n_success: 1,
    n_failure: -1,
    cache_hit_rate: 0.15,
    total_tokens: -2680,
    avg_total_latency_seconds: -0.87,
  },
};

export const cacheEntries: CacheEntry[] = [
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
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    },
    target_word_count: 775,
    cached_at: "2026-06-15T11:00:00",
    last_validated_at: "2026-06-15T11:00:00",
    validation_score: 0.94,
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
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    },
    target_word_count: 475,
    cached_at: "2025-12-01T10:00:00",
    last_validated_at: "2025-12-01T10:00:00",
    validation_score: 0.667,
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
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    },
    target_word_count: 775,
    cached_at: "2026-06-20T13:22:00",
    last_validated_at: "2026-06-20T13:22:00",
    validation_score: 0.88,
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
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    },
    target_word_count: 475,
    cached_at: "2026-06-22T16:40:00",
    last_validated_at: "2026-06-22T16:40:00",
    validation_score: 0.91,
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
      embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    },
    target_word_count: 775,
    cached_at: "2026-05-30T10:00:00",
    last_validated_at: "2026-05-30T10:00:00",
    validation_score: 0.71,
  },
];

const cacheQuestionTexts: Record<string, string> = {
  q001: "Discuss the management of diabetes mellitus.",
  q002: "Describe the epidemiology of tuberculosis in India.",
  q003: "What are the national health programmes for vector-borne diseases?",
  q014: "Describe the medico-legal autopsy procedure for a road-traffic fatality.",
  q021: "Discuss the toxicology, clinical features and management of organophosphate poisoning.",
};

export function getCacheEntryFull(qid: string): CacheEntryFull | undefined {
  const entry = cacheEntries.find((e) => e.qid === qid);
  if (!entry) return undefined;
  return {
    ...entry,
    module: entry.subject === "psm" ? "psm-module-1" : "fmt-module-1",
    chapter: "general",
    question_text: cacheQuestionTexts[qid] ?? "(question text unavailable)",
    answer_text: sampleAnswer,
    pdf_path: `/home/user/.medrack/cache/${entry.subject}/general/${qid}.pdf`,
    stale: entry.is_stale,
    embedding_model: "sentence-transformers/all-MiniLM-L6-v2",
    package_version: "0.3.0-backend-freeze",
  };
}

export const cacheStatus: CacheStatus = {
  schema_version: 1,
  total_entries: cacheEntries.length,
  by_subject: { psm: 3, fmt: 2 },
  stale_by_subject: { psm: 1, fmt: 1 },
};

export const logs: Record<LogName, LogEntry[]> = {
  ingestion: [
    {
      book_id: "park_psm_v4",
      status: "succeeded",
      started_at: "2026-01-15T10:25:00",
      finished_at: "2026-01-15T10:30:00",
      chunk_count: 1234,
      error: null,
    },
    {
      book_id: "park_fmt_v3",
      status: "succeeded",
      started_at: "2026-01-20T14:10:00",
      finished_at: "2026-01-20T14:15:00",
      chunk_count: 876,
      error: null,
    },
    {
      book_id: "kpark_clinical",
      status: "running",
      started_at: "2026-06-29T09:00:00",
      finished_at: null,
      chunk_count: 0,
      error: null,
    },
  ],
  generation: [
    {
      qid: "q001",
      subject: "psm",
      ok: true,
      token_count: 1234,
      latency_seconds: 5.6,
      cache_hit: false,
      timestamp: "2026-06-29T10:11:02",
    },
    {
      qid: "q002",
      subject: "psm",
      ok: true,
      token_count: 567,
      latency_seconds: 3.2,
      cache_hit: true,
      timestamp: "2026-06-29T10:14:18",
    },
    {
      qid: "q003",
      subject: "psm",
      ok: true,
      token_count: 1812,
      latency_seconds: 7.4,
      cache_hit: false,
      timestamp: "2026-06-29T10:18:55",
    },
    {
      qid: "q014",
      subject: "fmt",
      ok: true,
      token_count: 988,
      latency_seconds: 4.1,
      cache_hit: false,
      timestamp: "2026-06-29T10:24:01",
    },
  ],
  validation: [
    {
      qid: "q001",
      passed: true,
      score: 0.94,
      rule_count: 9,
      failed_count: 0,
      timestamp: "2026-06-29T10:11:08",
    },
    {
      qid: "q002",
      passed: false,
      score: 0.5,
      rule_count: 9,
      failed_count: 1,
      timestamp: "2026-06-29T10:14:19",
    },
    {
      qid: "q003",
      passed: true,
      score: 0.88,
      rule_count: 9,
      failed_count: 0,
      timestamp: "2026-06-29T10:18:59",
    },
  ],
  benchmark: [
    {
      run_id: "20260628T193408Z",
      n_questions: 20,
      n_success: 40,
      n_failure: 0,
      cache_hit_rate: 0.55,
      total_tokens: 18420,
      llm_mode: "real",
      timestamp: "2026-06-28T19:34:08Z",
    },
  ],
};

export const sampleQuestions = [
  {
    qid: "q001",
    question_text: "Discuss the management of diabetes mellitus.",
    subject: "psm" as const,
    marks: 10 as const,
  },
  {
    qid: "q002",
    question_text: "Describe the epidemiology of tuberculosis in India.",
    subject: "psm" as const,
    marks: 5 as const,
  },
  {
    qid: "q003",
    question_text: "What are the national health programmes for vector-borne diseases?",
    subject: "psm" as const,
    marks: 10 as const,
  },
  {
    qid: "q014",
    question_text: "Describe the medico-legal autopsy procedure for a road-traffic fatality.",
    subject: "fmt" as const,
    marks: 10 as const,
  },
  {
    qid: "q021",
    question_text:
      "Discuss the toxicology, clinical features and management of organophosphate poisoning.",
    subject: "fmt" as const,
    marks: 15 as const,
  },
];
