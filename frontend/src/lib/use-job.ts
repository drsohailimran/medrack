import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { JobStatus } from "@/lib/api";

// Polls an async backend job (book ingest / question-bank extract / solve)
// until it reaches a terminal state, exposing live progress for a bar.
//
// If a `storageKey` is passed, the active job id is persisted to
// localStorage and automatically resumed after a page reload — so the
// progress bar (and, for solves, the finished result) survive a refresh.
// A resumed job whose id the server no longer knows (e.g. the backend was
// restarted) is dropped silently instead of showing a spurious error.
export function useJob(storageKey?: string) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stop = useCallback(() => {
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  }, []);

  const clearStorage = useCallback(() => {
    if (storageKey) {
      try {
        localStorage.removeItem(storageKey);
      } catch {
        /* ignore */
      }
    }
  }, [storageKey]);

  const reset = useCallback(() => {
    stop();
    clearStorage();
    setJob(null);
  }, [stop, clearStorage]);

  const poll = useCallback(
    (jobId: string, isResume: boolean) => {
      stop();
      let misses = 0;
      let settledOnce = false;
      const tick = async () => {
        try {
          const s = await api.getJob(jobId);
          misses = 0;
          settledOnce = true;
          setJob(s);
          if (s.status === "done" || s.status === "error") stop();
        } catch {
          // A resumed job that can't be fetched on the first attempt was
          // almost certainly lost to a server restart — drop it quietly.
          if (isResume && !settledOnce) {
            stop();
            clearStorage();
            setJob(null);
            return;
          }
          misses += 1;
          if (misses >= 6) {
            stop();
            setJob((cur) =>
              cur ? { ...cur, status: "error", error: "Lost connection to the server." } : cur,
            );
          }
        }
      };
      void tick();
      timer.current = setInterval(tick, 800);
    },
    [stop, clearStorage],
  );

  const start = useCallback(
    (jobId: string) => {
      if (storageKey) {
        try {
          localStorage.setItem(storageKey, jobId);
        } catch {
          /* ignore */
        }
      }
      setJob({
        schema_version: 1,
        job_id: jobId,
        kind: "",
        status: "pending",
        percent: 0,
        message: "Starting…",
        result: null,
        error: null,
      });
      poll(jobId, false);
    },
    [poll, storageKey],
  );

  // Resume a persisted job after a page reload.
  useEffect(() => {
    if (!storageKey) return;
    let saved: string | null = null;
    try {
      saved = localStorage.getItem(storageKey);
    } catch {
      /* ignore */
    }
    if (saved) {
      setJob({
        schema_version: 1,
        job_id: saved,
        kind: "",
        status: "pending",
        percent: 0,
        message: "Reconnecting…",
        result: null,
        error: null,
      });
      poll(saved, true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  useEffect(() => () => stop(), [stop]);

  return { job, start, stop, reset };
}
