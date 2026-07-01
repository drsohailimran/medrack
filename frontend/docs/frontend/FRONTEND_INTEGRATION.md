# Frontend Integration Guide

This document describes exactly how the frontend should
communicate with the MedRack backend. It is the **integration
reference** for the production frontend.

## API versioning

The MedRack API is **frozen at v1**. The base URL is:

```
http://localhost:8000/api/v1
```

The frontend should **always** pin to `/api/v1`. Do not call
`/api/v2/` (it does not exist). If a future phase adds a
v2, the frontend will be informed via a new ADR and a new
handoff package.

### Versioning of response data

Every successful response includes a `schema_version: 1`
field. The frontend can:
- Ignore `schema_version` (safe; v1 is the only version)
- Check `schema_version === 1` and show a warning if it
  differs (defensive; future-proof)

The frontend should **not** attempt to call v2 endpoints or
expect v2 fields. v1 is the contract.

## Authentication strategy (future-ready)

**v1 has no authentication.** The API is open. The operator
should add network-level access control (firewall, VPN,
reverse proxy with auth) for production deployments.

### Future plan (not in v1)

When authentication is added, the recommended approach is
OAuth/PKCE (e.g. via the `oauth-pkce-over-ssh` skill). The
frontend will:
1. Redirect the user to the OAuth provider
2. Receive an access token + refresh token
3. Send `Authorization: Bearer {access_token}` on every API
  call
4. Refresh the token when it expires

The frontend should be designed with this in mind: a
single `apiClient` function that adds the `Authorization`
header from a context-provided token. The actual auth flow
is not in v1.

For now, the frontend should:
- NOT send any auth header
- NOT have a login screen
- Assume the API is open

## Timeout handling

Different endpoints have different expected latencies:

| Endpoint | Expected latency | Recommended timeout |
|----------|------------------|----------------------|
| `GET /api/v1/version` | <100ms | 5s |
| `GET /api/v1/library/books` | <100ms | 5s |
| `GET /api/v1/library/ingestion-status/{id}` | <100ms | 5s |
| `GET /api/v1/cache/entries` | <500ms | 10s |
| `GET /api/v1/cache/entries/{qid}` | <200ms | 5s |
| `GET /api/v1/cache/status` | <100ms | 5s |
| `GET /api/v1/benchmarks/runs` | <500ms | 10s |
| `GET /api/v1/benchmarks/runs/{id}` | <500ms | 10s |
| `GET /api/v1/benchmarks/compare` | <500ms | 10s |
| `GET /api/v1/pipeline/inspect` | <500ms | 30s |
| `GET /api/v1/logs/{name}` | <200ms | 5s |
| `GET /api/v1/logs/{name}/search` | <500ms | 10s |
| `POST /api/v1/library/books` | <500ms | 30s |
| `DELETE /api/v1/library/books/{id}` | <500ms | 10s |
| `POST /api/v1/library/books/{id}/reindex` | <500ms | 30s |
| `POST /api/v1/questions/generate` | 5-30s | 60s |
| `POST /api/v1/questions/batch` | 100-600s | 900s |
| `POST /api/v1/questions/{qid}/revise` | 5-30s | 60s |
| `POST /api/v1/validation/validate` | <1s | 30s |
| `POST /api/v1/cache/reanswer` | <500ms | 10s |

The frontend should configure fetch/axios with these
timeouts. On timeout, show a "Backend slow" message and
allow retry.

## Retry policy

| Status code | Retry? | Reason |
|-------------|--------|--------|
| 200 | n/a | success |
| 400 | no | bad request; fix and retry |
| 404 | no | not found; refresh the data and stop |
| 422 | no | validation error; fix and retry |
| 5xx | yes, 1 retry after 2s | transient server error |
| Timeout | yes, 1 retry after 2s | transient network error |

The retry should be exponential with a 2s delay (not
exponential backoff, just 1 retry). If the second attempt
also fails, show the error to the user.

The frontend should NOT retry mutations on 4xx (these are
client errors; retrying doesn't help).

## Polling strategy

Polling is needed for long-running operations:

| Operation | Endpoint | Interval | Stop when |
|-----------|----------|----------|-----------|
| Ingestion status | `GET /api/v1/library/ingestion-status/{id}` | 5s | `status` is `succeeded` or `failed` |
| Question generation | n/a (single call) | n/a | n/a |
| Batch generation | n/a (single call) | n/a | n/a |
| Stale list refresh | n/a (user action) | n/a | n/a |
| Re-answer | n/a (single call) | n/a | n/a |
| Benchmark | n/a (single call) | n/a | n/a |

Polling should stop on:
- Terminal status (succeeded/failed)
- Component unmount (React Query does this automatically)
- 10-minute timeout (fail gracefully)

## Long-running jobs

The `/api/v1/questions/generate` endpoint takes 5-30 seconds
with a real LLM. The frontend should:
- Show a spinner with text "Generating answer..."
- Disable the "Generate" button (no double-submit)
- Allow the user to navigate away (the request continues
  server-side)
- On return to the Generate page, refetch the result

The `/api/v1/questions/batch` endpoint takes 100-600 seconds
for 20 questions. Same UX.

In v1, there is **no cancel** mechanism. The user must wait.

## Streaming support (if applicable)

v1 has **no streaming**. All endpoints are request/response.

Future: if the backend adds Server-Sent Events (SSE) or
WebSocket support, the frontend should add EventSource or
WebSocket clients. For now, the frontend should use polling
or single calls.

## PDF downloads

The `pdf_path` field in `GenerationResult` and `CacheEntry`
is an **absolute filesystem path** on the backend host. The
frontend cannot directly open this URL.

Options for the frontend:
1. **Show a "Download PDF" button** that triggers the
   backend to copy the PDF to a public URL (not in v1)
2. **Embed the PDF via iframe** using a custom URL
   (not in v1)
3. **Tell the user the PDF is on the backend host** at
   `/path/to/q001.pdf` and let them download it via their
   own file manager

For now, the frontend should use option 3. The user
already has filesystem access to the backend host (the
operator is one person running a local app).

A future API endpoint can serve PDFs over HTTP
(e.g. `GET /api/v1/cache/entries/{qid}/pdf`). This is **not
in v1**.

## Cache invalidation

When a mutation succeeds, the frontend should invalidate the
relevant queries. See `STATE_MANAGEMENT.md` for the full
table. Summary:

| Mutation | Invalidate |
|----------|------------|
| `useAddBook` | `['library', 'books']` |
| `useRemoveBook` | `['library', 'books']`, `['cache', 'status']` |
| `useReindex` | `['library', 'books']`, `['library', 'ingestion-status', bookId]` |
| `useGenerateAnswer` | `['cache', 'entries']`, `['cache', 'status']`, `['questions', qid, 'cached']` |
| `useReviseAnswer` | `['cache', 'entries', qid]`, `['cache', 'status']` |
| `useReanswer` | `['cache', 'entries']`, `['cache', 'entries', qid]`, `['cache', 'status']` |

## Error handling

All errors use the shape:
```json
{
  "error_code": "RUN_NOT_FOUND",
  "detail": "benchmark run not found: my-run-id"
}
```

The frontend should:
1. Switch on `error_code` for known errors (e.g. show a
   specific message for `CACHE_ENTRY_NOT_FOUND`)
2. Fall back to `detail` for unknown errors
3. Map to user-friendly messages; never show raw JSON

Recommended error-message map:

| error_code | User message |
|------------|--------------|
| `RUN_NOT_FOUND` | "This benchmark run no longer exists. The list has been refreshed." |
| `CACHE_ENTRY_NOT_FOUND` | "This cached answer no longer exists. The list has been refreshed." |
| `UNKNOWN_LOG` | "Invalid log name. Valid logs: ingestion, generation, validation, benchmark." |
| (FastAPI 422) | Show validation errors field-by-field |
| (any 5xx) | "Backend error. Please try again." |
| (timeout) | "The backend is taking too long. Please try again." |
| (network) | "Cannot reach the backend. Check that MedRack is running." |

## Offline behavior (where applicable)

The MedRack backend is a local server. The frontend can
assume it's reachable. Offline behavior is not in v1.

If the operator wants offline support in the future, they
would need:
- A service worker to cache API responses
- A "Sync when online" button
- Clear offline indicators

For now, the frontend should fail loudly if the backend is
unreachable (a full-page error screen).

## Recommended client setup

```typescript
// src/api/client.ts
const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL ||
  process.env?.REACT_APP_API_BASE_URL ||
  'http://localhost:8000/api/v1';

const TIMEOUTS = {
  fast: 5_000,
  medium: 10_000,
  generate: 60_000,
  batch: 900_000,
  inspect: 30_000,
  validate: 30_000,
};

async function request<T>(
  method: string,
  path: string,
  body?: any,
  timeout = TIMEOUTS.medium,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      // Authorization will be added in a future version
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: controller.signal,
  });

  clearTimeout(timer);

  if (!res.ok) {
    // Try to parse the error response
    let err: any;
    try {
      err = await res.json();
    } catch {
      err = { error_code: 'UNKNOWN', detail: res.statusText };
    }
    err.status = res.status;
    throw err;
  }

  return res.json();
}

// Public API
export const api = {
  // Library
  listBooks: () => request('GET', '/library/books', undefined, TIMEOUTS.fast),
  addBook: (pdf_path: string, subject: string, book_title?: string) =>
    request('POST', `/library/books?pdf_path=${encodeURIComponent(pdf_path)}&subject=${subject}&book_title=${book_title || ''}`, undefined, TIMEOUTS.medium),
  removeBook: (book_id: string) => request('DELETE', `/library/books/${book_id}`, undefined, TIMEOUTS.medium),
  reindexBook: (book_id: string) => request('POST', `/library/books/${book_id}/reindex`, undefined, TIMEOUTS.medium),
  getIngestionStatus: (book_id: string) => request('GET', `/library/ingestion-status/${book_id}`, undefined, TIMEOUTS.fast),
  listQuestionBanks: () => request('GET', '/library/question-banks', undefined, TIMEOUTS.fast),

  // Questions
  generateAnswer: (req: any) => request('POST', '/questions/generate', req, TIMEOUTS.generate),
  generateBatch: (req: any) => request('POST', '/questions/batch', req, TIMEOUTS.batch),
  reviseAnswer: (qid: string, req: any) => request('POST', `/questions/${qid}/revise`, req, TIMEOUTS.generate),
  listStaleAnswers: (module_name: string, dry_run: boolean) =>
    request('GET', `/questions/stale?module_name=${module_name}&dry_run=${dry_run}`, undefined, TIMEOUTS.medium),

  // Pipeline
  inspectPipeline: (params: any) => {
    const q = new URLSearchParams(params).toString();
    return request('GET', `/pipeline/inspect?${q}`, undefined, TIMEOUTS.inspect);
  },

  // Validation
  validateAnswer: (req: any) => request('POST', '/validation/validate', req, TIMEOUTS.validate),

  // Benchmarks
  listBenchmarkRuns: () => request('GET', '/benchmarks/runs', undefined, TIMEOUTS.medium),
  getBenchmarkRun: (run_id: string) => request('GET', `/benchmarks/runs/${run_id}`, undefined, TIMEOUTS.medium),
  compareBenchmarkRuns: (run_a: string, run_b: string) =>
    request('GET', `/benchmarks/compare?run_a=${run_a}&run_b=${run_b}`, undefined, TIMEOUTS.medium),

  // Cache
  listCacheEntries: (params: { subject?: string; stale_only?: boolean }) => {
    const q = new URLSearchParams(params as any).toString();
    return request('GET', `/cache/entries?${q}`, undefined, TIMEOUTS.medium);
  },
  getCacheEntry: (qid: string) => request('GET', `/cache/entries/${qid}`, undefined, TIMEOUTS.fast),
  getCacheStatus: () => request('GET', '/cache/status', undefined, TIMEOUTS.fast),
  reanswer: (qid: string) => request('POST', '/cache/reanswer', { qid }, TIMEOUTS.medium),

  // Version
  getVersion: () => request('GET', '/version', undefined, TIMEOUTS.fast),

  // Logs
  tailLog: (name: string, n = 100) => request('GET', `/logs/${name}?n=${n}`, undefined, TIMEOUTS.fast),
  searchLog: (name: string, query: string, n = 100) =>
    request('GET', `/logs/${name}/search?query=${encodeURIComponent(query)}&n=${n}`, undefined, TIMEOUTS.medium),
};
```

## Summary

| Concern | Recommendation |
|---------|----------------|
| API version | Pin to `/api/v1` |
| Auth | None in v1; design for OAuth/PKCE future |
| Timeout | 5-30s for fast endpoints, 60-900s for slow |
| Retry | 1 retry on 5xx and timeout |
| Polling | 5s for ingestion; no polling elsewhere |
| Cancellation | Not supported in v1 |
| Streaming | Not supported in v1 |
| PDF | User downloads via their own file manager |
| Cache invalidation | See table above |
| Errors | Use the consistent `error_code` + `detail` shape |
| Offline | Not supported in v1 |

## Open questions for the operator

If the operator encounters a frontend requirement that
cannot be satisfied by the current API, document it in the
integration report. Do not invent backend behavior.

Common questions:
- "How do I display a PDF in the browser?" — not in v1.
  Add `GET /api/v1/cache/entries/{qid}/pdf` if needed.
- "How do I cancel a long-running generation?" — not in v1.
  Add `POST /api/v1/questions/{qid}/cancel` if needed.
- "How do I stream progress for a batch?" — not in v1.
  Add WebSocket/SSE support if needed.
- "How do I authenticate users?" — not in v1.
  Add OAuth/PKCE if needed.
- "How do I limit rate?" — add at the reverse proxy layer.

Each of these is a separate endpoint addition. None are in
v1.
