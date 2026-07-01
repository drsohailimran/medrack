# MedRack Pipeline Flow

This document traces a question through the MedRack pipeline,
from input to canonical cached answer. It is intended for
engineers who need to understand the data flow at each stage.

## End-to-end flow

```
1. Question input
   ↓
2. Question analysis (marks, sections)
   ↓
3. Strategy (top_k, metadata filter)
   ↓
4. Vector index query (raw chunks)
   ↓
5. Metadata-boost rerank
   ↓
6. Semantic rerank
   ↓
7. Planner (blueprint)
   ↓
8. Blueprint Retrieval spec
   ↓
9. Writer (prompt + LLM + render)
   ↓
10. Validator (9 rules)
   ↓
11. Cache (canonical)
   ↓
12. PDF output
```

## Example: end-to-end

Let's trace a 10-mark PSM question through the pipeline.

### 1. Question input

```python
question = {
    "qid": "q001",
    "question_text": "Discuss the management of diabetes mellitus.",
}
subject = "psm"
marks = 10
```

### 2. Question analysis

The `QuestionAnalyzer` inspects the question text and produces
a `QuestionAnalysis`:

```python
analysis = QuestionAnalysis(
    marks=10,
    target_sections=["section_management", "section_epidemiology"],
    subject="psm",
)
```

The analyzer detects "management" and "epidemiology" in the
question text using the same vocabulary as the metadata
extractor (Phase 6).

### 3. Strategy

The `AdaptiveStrategy` decides:

- `top_k = 8` (10-mark question)
- `metadata_filter`: single-section filter for `section_management`
  (only 1 target section, so the filter is used)

### 4. Vector index query

The `medrack.ingest.index.query` function retrieves the top 8
chunks from `kb_psm` (the vector index for PSM) that match the
question embedding AND the metadata filter.

```python
raw_results = [
    {"id": "chunk_001", "text": "...", "metadata": {"section_management": True, ...}, "distance": 0.42},
    {"id": "chunk_002", "text": "...", "metadata": {"section_definition": True, ...}, "distance": 0.51},
    ...
]
```

### 5. Metadata-boost rerank

The `MetadataBoostReranker` (Phase 7) re-orders the chunks by
boosting those whose metadata flags match the detected sections:

- Chunks with `section_management=True` get their distance
  reduced (boost factor: 0.67)
- Other chunks are unchanged

### 6. Semantic rerank

The `HeuristicReranker` (Phase 10, default `IdentityReranker`)
optionally re-orders by semantic relevance. By default it's a
no-op; operators can opt in to a heuristic or a real cross-
encoder.

### 7. Planner

The `DeterministicPlanner` produces a `Blueprint`:

```python
blueprint = Blueprint(
    subject="psm",
    marks=10,
    question_type="theory",
    target_word_count=775,
    sections=[
        Section(name="introduction", target_word_count=116, required=True, category=FRAMING),
        Section(name="definition", target_word_count=150, required=True, category=MEDICAL, metadata_section="section_definition"),
        Section(name="epidemiology", target_word_count=150, required=True, category=MEDICAL, metadata_section="section_epidemiology"),
        Section(name="management", target_word_count=290, required=True, category=MEDICAL, metadata_section="section_management"),
        Section(name="conclusion", target_word_count=78, required=True, category=FRAMING),
    ],
    required_metadata_categories=["section_definition", "section_epidemiology", "section_management"],
)
```

### 8. Blueprint Retrieval spec

The `build_blueprint_retrieval` function produces a
`BlueprintRetrieval` spec:

```python
spec = BlueprintRetrieval(
    subject="psm",
    marks=10,
    total_target_word_count=775,
    section_specs=[
        SectionRetrievalSpec(section_name="introduction", priority=0, min_chunks=1, max_chunks=3, evidence_category="framing"),
        SectionRetrievalSpec(section_name="definition", priority=0, min_chunks=1, max_chunks=3, evidence_category="medical", metadata_filter=...),
        ...
    ],
    aggregate_metadata_filter=...,
    evidence_categories=["medical", "framing"],
)
```

### 9. Writer

The `generate_answer` function:

1. Looks up the question in the cache (`answer/cache.py`)
2. If cache miss, builds the prompt from the blueprint
3. Calls the LLM
4. Renders the answer to PDF
5. Returns the result

```python
result = generate_answer(
    question={"qid": "q001", "question_text": "..."},
    subject="psm",
    llm_client=llm,
    marks=10,
)
# {
#   "qid": "q001",
#   "answer_text": "Introduction: ...\nManagement: ...\nConclusion: ...",
#   "pdf_path": "/home/.../q001.pdf",
#   "cache_hit": False,
#   "token_count": 1234,
# }
```

### 10. Validator

The `ValidationPipeline` runs 9 rules against the answer:

```python
report = ValidationPipeline().validate(result["answer_text"], blueprint)
# {
#   "schema_version": 1,
#   "pass": true,
#   "score": 0.778,
#   "results": [...9 rule verdicts...],
#   "failed_rules": [],
#   "warnings": [],
# }
```

### 11. Cache

If the validation passed, the answer is stored in the canonical
cache. If it failed, the answer is still cached but marked as
`stale: true` with the failure reasons.

### 12. PDF

The `render_to_pdf` function produces a PDF from the answer
text. The PDF is stored at the cache path.

## End-to-end latency

A typical mock-LLM generation takes ~0.17s (cache warm path)
or ~5-10s (cache cold path with real LLM). The breakdown:

- Question analysis: <1ms
- Vector query: ~50ms
- Metadata rerank: <1ms
- Semantic rerank: <1ms
- Planner: <1ms
- Blueprint spec: <1ms
- LLM call: 5-30s (real) or <1ms (mock)
- PDF render: ~5ms
- Validation: <1ms
- Cache write: <1ms

## Errors and retries

The pipeline is **fail-fast**: any unrecoverable error aborts
the generation. Common errors:

- **No chunks retrieved**: the vector index has no matches
  for the question. Action: ingest more books.
- **LLM API error**: the LLM call failed. Action: retry or
  fall back to the mock LLM.
- **Validation failed**: the answer doesn't meet the rules.
  Action: the answer is cached as `stale` and the operator
  decides whether to revise or re-answer.

## Caching

The cache is **canonical** when the answer passes validation.
Failed answers are stored but marked `stale`. Stale answers
remain available for inspection; they never silently disappear.

The cache uses **versioned keys**: a cache hit requires the
schema, prompt, retrieval, planner, validator, reranker, and
renderer versions to match. A version mismatch marks the
answer as stale (Phase 3).

See `cache.md` for the full cache contract.
