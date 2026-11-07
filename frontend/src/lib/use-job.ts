import { useEffect, useRef, useState } from "react";
import { get } from "./api-client";
import type { JobOut } from "./api-types";

const TERMINAL = new Set(["succeeded", "failed", "cancelled"]);

/** Poll a durable job until it reaches a terminal state. */
export function useJob(jobId: string | null, intervalMs = 2000) {
  const [job, setJob] = useState<JobOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (!jobId) {
      setJob(null);
      return;
    }
    let cancelled = false;
    const controller = new AbortController();
    async function poll() {
      try {
        const current = await get<JobOut>(`/api/v1/jobs/${jobId}`, controller.signal);
        if (cancelled) return;
        setJob(current);
        setError(null);
        if (!TERMINAL.has(current.status)) {
          timer.current = window.setTimeout(poll, intervalMs);
        }
      } catch (err: unknown) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Job lookup failed.");
      }
    }
    poll();
    return () => {
      cancelled = true;
      controller.abort();
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [jobId, intervalMs]);

  return { job, error };
}
