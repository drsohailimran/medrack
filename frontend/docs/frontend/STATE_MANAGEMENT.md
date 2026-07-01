# State Management (Frontend)

This document recommends a state management strategy for the
MedRack frontend. The recommendation is **React Query** (also
known as TanStack Query) with a thin wrapper around it.

## Why React Query?

The MedRack backend is an HTTP API with 22 endpoints. Most
endpoints are read-only and have natural caching semantics.
React Query is designed for exactly this use case.

Alternatives considered:
- **Redux / Zustand / Jotai**: too low-level for a
  server-state-heavy app
- **SWR**: similar to React Query; React Query is more
  popular and has more features
- **Plain fetch + useState**: works but reinvents React Query
  poorly

## Recommended setup

```typescript
// src/api/client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Most backend data is fresh enough; cache for 30s by default
      staleTime: 30_000,
      // Retry once on 5xx, don't retry on 4xx
      retry: (failureCount, error) => {
        if (error?.status >= 400 && error?.status < 500) return false;
        return failureCount < 1;
      },
      // Refetch on window focus
      refetchOnWindowFocus: true,
    },
    mutations: {
      // Mutations don't retry by default
      retry: false,
    },
  },
});
```

## Query keys

Use a consistent query-key convention:

```typescript
// Library
['library', 'books']
['library', 'books', bookId]
['library', 'ingestion-status', bookId]
['library', 'question-banks']

// Questions
['questions', qid, 'cached']  // GET /api/v1/cache/entries/{qid}
['questions', 'stale', moduleName, dryRun]

// Pipeline
['pipeline', qid, subject, marks]  // GET /api/v1/pipeline/inspect

// Validation
['validation', answerHash, disabledRules]

// Benchmarks
['benchmarks', 'runs']
['benchmarks', 'runs', runId]
['benchmarks', 'compare', runA, runB]

// Cache
['cache', 'entries', subject, staleOnly]
['cache', 'entries', qid]
['cache', 'status']

// Version
['version']

// Logs
['logs', name, n]
['logs', name, 'search', query, n]
```

## API hooks

```typescript
// src/api/hooks.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from './client';

export function useBooks() {
  return useQuery({
    queryKey: ['library', 'books'],
    queryFn: () => api.listBooks(),
  });
}

export function useIngestionStatus(bookId: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['library', 'ingestion-status', bookId],
    queryFn: () => api.getIngestionStatus(bookId),
    // Poll every 5s while not succeeded/failed
    refetchInterval: (data) => {
      if (!data) return 5000;
      if (data.status === 'succeeded' || data.status === 'failed') return false;
      return 5000;
    },
    enabled: options?.enabled !== false,
  });
}

export function useGenerateAnswer() {
  return useMutation({
    mutationFn: (req: api.GenerateRequest) => api.generateAnswer(req),
  });
}

export function useCacheEntry(qid: string) {
  return useQuery({
    queryKey: ['cache', 'entries', qid],
    queryFn: () => api.getCacheEntry(qid),
    enabled: !!qid,
  });
}

// ... etc.
```

## Polling strategy

| Resource | When to poll | Interval |
|----------|--------------|----------|
| Ingestion status | while `status` is `pending` or `running` | 5s |
| Generate | n/a (single call) | n/a |
| Batch | n/a (single call) | n/a |
| Stale list | on user action | n/a |
| Benchmark runs | on user action | n/a |
| Logs | on user action | n/a |

For ingestion polling, use the `refetchInterval` callback
pattern (shown above) so polling stops automatically when
the status is terminal.

## Cache invalidation

Mutations should invalidate the relevant queries:

```typescript
export function useReanswer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (qid: string) => api.reanswer(qid),
    onSuccess: (_, qid) => {
      // Invalidate the cache list and the specific entry
      qc.invalidateQueries({ queryKey: ['cache', 'entries'] });
      qc.invalidateQueries({ queryKey: ['cache', 'entries', qid] });
      qc.invalidateQueries({ queryKey: ['cache', 'status'] });
    },
  });
}
```

Other invalidation rules:
- `useGenerateAnswer` on success → invalidate `['cache', 'entries']`, `['cache', 'status']`, `['questions', qid, 'cached']`
- `useReviseAnswer` on success → invalidate `['cache', 'entries', qid]`, `['cache', 'status']`
- `useAddBook` on success → invalidate `['library', 'books']`
- `useRemoveBook` on success → invalidate `['library', 'books']`, `['cache', 'status']`
- `useReindex` on success → invalidate `['library', 'books']`, `['library', 'ingestion-status', bookId]`

## Optimistic updates

The MedRack API doesn't have many actions that benefit from
optimistic updates (most are server-driven). But for the
"re-answer" action, optimistic updates make sense:

```typescript
export function useReanswer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (qid: string) => api.reanswer(qid),
    onMutate: async (qid) => {
      await qc.cancelQueries({ queryKey: ['cache', 'entries', qid] });
      const prev = qc.getQueryData(['cache', 'entries', qid]);
      qc.setQueryData(['cache', 'entries', qid], (old: any) => ({
        ...old,
        is_stale: true,
        stale_reasons: ['reanswer'],
      }));
      return { prev };
    },
    onError: (_, __, ctx) => {
      qc.setQueryData(['cache', 'entries', ctx?.prev?.qid], ctx?.prev);
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['cache', 'entries'] });
    },
  });
}
```

## Loading states

Use the `isLoading` and `isFetching` flags from React Query:

- `isLoading` — the query is fetching for the first time
  (no cached data). Show a full-page skeleton.
- `isFetching` — the query is fetching in the background
  (cached data exists). Show a small refresh indicator.
- `isError` — the query failed. Show an error message with
  a retry button.

## Error states

React Query provides the `error` object. Map it to a user-
friendly message:

```typescript
function getErrorMessage(error: any): string {
  if (!error) return 'Unknown error';
  if (error.status === 404) {
    return 'Not found';
  }
  if (error.status === 400) {
    return error.body?.detail || 'Invalid request';
  }
  if (error.status >= 500) {
    return 'Backend error. Please try again.';
  }
  return error.message || 'Unknown error';
}
```

## Empty states

Most pages should handle three empty states:

1. **Initial empty** — no data has been loaded yet
2. **Filtered empty** — data exists but the filter returns 0
   results (e.g. `stale_only=true` with no stale entries)
3. **Error empty** — the query failed

## Background generation (future)

In v1, the batch endpoint is synchronous (the user waits for
the entire response). A future phase may add a background-
generation endpoint that returns a job_id immediately and
allows polling for status. The frontend would then use:

- A `useJobStatus` hook that polls every 5s
- A toast notification when the job completes
- A "View results" link in the notification

For now, use the synchronous endpoint and show a long-
running spinner.

## Offline behavior (future)

The MedRack backend is a local server, so the frontend can
assume it's reachable. Offline behavior is not in v1.

If the operator wants offline support, future work would
need:
- A service worker to cache API responses
- A "Sync when online" button
- Clear offline indicators

## Summary

| Concern | Recommendation |
|---------|----------------|
| Server state | React Query |
| Client state (UI) | useState / useReducer / Context |
| Long-running state | React Query `refetchInterval` |
| Form state | React Hook Form (or similar) |
| Routing | React Router (or Next.js) |
| Styling | Tailwind CSS (or Material UI / Chakra) |
| Auth (future) | OAuth/PKCE (see `oauth-pkce-over-ssh` skill) |
