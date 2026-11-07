import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { post } from "../../lib/api-client";
import type { JobOut } from "../../lib/api-types";
import { useJob } from "../../lib/use-job";
import { ErrorNotice } from "../../components/ui";
import type { SearchHit } from "./types";

export function ImportControl({ hit, crewId }: { hit: SearchHit; crewId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const lock = useRef(false);
  const idempotencyKey = useRef(crypto.randomUUID());
  const { job, error } = useJob(jobId);
  async function start() {
    if (lock.current) return;
    lock.current = true; setStarting(true); setStartError(null);
    try {
      const response = await post<JobOut>("/api/v1/imports", { provider: hit.provider, external_id: hit.external_id, crew_id: crewId, idempotency_key: idempotencyKey.current });
      setJobId(response.id);
    } catch (err) { setStartError(err instanceof Error ? err.message : "Import failed to start."); }
    finally { lock.current = false; setStarting(false); }
  }
  if (error) return <ErrorNotice message={error} onRetry={() => { setJobId(null); }} />;
  if (job?.status === "succeeded") {
    const result = job.result as { track_id?: string; warnings?: string[]; reused?: boolean } | null;
    return <div role="status" className="feedback">Imported{result?.reused ? " (already in the library)" : ""}. {result?.track_id && <Link to={`/tracks/${result.track_id}`}>Open the track</Link>}{result?.warnings?.map((warning, i) => <p key={i}>{warning}</p>)}</div>;
  }
  if (job?.status === "failed" || job?.status === "cancelled") return <ErrorNotice message={`Import ${job.status}: ${job.error ?? "No result"}. Check the library before starting another import.`} />;
  if (jobId) return <p className="feedback" role="status">Importing… {Math.round((job?.progress ?? 0) * 100)}% {job?.wait_reason}</p>;
  return <>{startError && <ErrorNotice message={startError} />}<button type="button" disabled={starting} onClick={() => void start()}>{starting ? "Starting import…" : `Import “${hit.title ?? hit.external_id}” to the library`}</button></>;
}
