import { useState } from "react";
import { ApiError, post } from "../../lib/api-client";
import { useGet } from "../../lib/use-api";
import type { JobOut } from "../../lib/api-types";
import { ErrorNotice, Loading } from "../../components/ui";

export function JobsPanel() {
  const { data, error, loading, reload } = useGet<{ items: JobOut[]; total: number }>(
    "/api/v1/admin/jobs?limit=30",
  );
  const [notice, setNotice] = useState<string | null>(null);

  async function cancel(id: string) {
    setNotice(null);
    try {
      await post(`/api/v1/jobs/${id}/cancel`, {});
      setNotice("Cancellation requested.");
      reload();
    } catch (err: unknown) {
      setNotice(err instanceof ApiError ? err.message : "Cancel failed.");
    }
  }

  if (loading) return <Loading label="Loading jobs…" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;

  return (
    <section aria-label="Jobs">
      <h3>Recent jobs</h3>
      {notice && <p role="status">{notice}</p>}
      {(data?.items ?? []).length === 0 && <p role="status">No jobs yet.</p>}
      <ul>
        {(data?.items ?? []).map((job) => (
          <li key={job.id}>
            {job.kind} — {job.status} ({Math.round(job.progress * 100)}%)
            {job.wait_reason ? ` — ${job.wait_reason}` : ""}
            {job.error ? ` — error: ${job.error.slice(0, 160)}` : ""}
            {(job.status === "queued" || job.status === "running") && (
              <>
                {" "}
                <button type="button" onClick={() => void cancel(job.id)}>
                  Cancel
                </button>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
