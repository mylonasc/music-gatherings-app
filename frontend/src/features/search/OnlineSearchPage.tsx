import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, post } from "../../lib/api-client";
import type { JobOut } from "../../lib/api-types";
import { useGet } from "../../lib/use-api";
import { useJob } from "../../lib/use-job";
import { ErrorNotice, Field, Page } from "../../components/ui";

const PROVIDERS = ["fake", "lrclib", "ultimate_guitar"] as const;

interface SearchHit {
  provider: string;
  external_id: string;
  title: string | null;
  artist: string | null;
  artifact_types: string[];
  source_url: string | null;
  attribution: string | null;
  warnings?: string[];
}

export function OnlineSearchPage() {
  const { data: crews } = useGet<{ id: string; name: string }[]>("/api/v1/crews");
  const crewId = crews && crews.length > 0 ? crews[0].id : null;
  const [query, setQuery] = useState("");
  const [providers, setProviders] = useState<string[]>(["fake"]);
  const [searchJobId, setSearchJobId] = useState<string | null>(null);
  const [importJobs, setImportJobs] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const { job: searchJob, error: searchJobError } = useJob(searchJobId);

  async function startSearch(event: FormEvent) {
    event.preventDefault();
    if (!crewId || !query.trim() || providers.length === 0) return;
    setStarting(true);
    setSubmitError(null);
    setSearchJobId(null);
    try {
      const job = await post<JobOut>("/api/v1/search/online", {
        query: query.trim(),
        providers,
        crew_id: crewId,
      });
      setSearchJobId(job.id);
    } catch (err: unknown) {
      setSubmitError(err instanceof ApiError ? err.message : "Search failed to start.");
    } finally {
      setStarting(false);
    }
  }

  async function importHit(hit: SearchHit) {
    if (!crewId) return;
    try {
      const job = await post<JobOut>("/api/v1/imports", {
        provider: hit.provider,
        external_id: hit.external_id,
        crew_id: crewId,
      });
      setImportJobs((prev) => ({ ...prev, [`${hit.provider}:${hit.external_id}`]: job.id }));
    } catch (err: unknown) {
      setSubmitError(err instanceof ApiError ? err.message : "Import failed to start.");
    }
  }

  const results: SearchHit[] =
    searchJob?.status === "succeeded"
      ? Object.entries((searchJob.result as { results?: Record<string, SearchHit[]> })?.results ?? {}).flatMap(
          ([provider, items]) => items.map((item) => ({ ...item, provider })),
        )
      : [];

  function displayHit(hit: SearchHit): string {
    if (hit.title && hit.artist) return `${hit.title} — ${hit.artist}`;
    return hit.title ?? "Untitled";
  }

  return (
    <Page title="Online search">
      <p>
        Discovery only: searching never changes your library. Importing is a separate,
        explicit step.
      </p>
      {crewId === null && <p role="status">Join a crew before searching online.</p>}
      <form onSubmit={startSearch} aria-label="Online provider search">
        {submitError && <ErrorNotice message={submitError} />}
        <Field id="online-query" label="Song or artist">
          <input
            id="online-query"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Blue Train"
          />
        </Field>
        <fieldset>
          <legend>Providers</legend>
          {PROVIDERS.map((provider) => (
            <label key={provider} htmlFor={`provider-${provider}`}>
              <input
                id={`provider-${provider}`}
                type="checkbox"
                checked={providers.includes(provider)}
                onChange={(e) =>
                  setProviders((prev) =>
                    e.target.checked ? [...prev, provider] : prev.filter((p) => p !== provider),
                  )
                }
              />{" "}
              {provider === "lrclib" ? "LRCLIB" : provider.replaceAll("_", " ")}
            </label>
          ))}
        </fieldset>
        <button type="submit" disabled={starting || !crewId}>
          {starting ? "Starting…" : "Search online"}
        </button>
      </form>

      {searchJob && searchJob.status !== "succeeded" && searchJob.status !== "failed" && (
        <p role="status">
          Searching… {Math.round(searchJob.progress * 100)}%
          {searchJob.wait_reason ? ` (${searchJob.wait_reason})` : ""}
        </p>
      )}
      {searchJobError && <ErrorNotice message={searchJobError} />}
      {searchJob?.status === "failed" && (
        <ErrorNotice message={`Search failed: ${searchJob.error ?? "unknown error"}`} />
      )}
      {searchJob?.status === "succeeded" && results.length === 0 && (
        <p role="status">No provider results. Try different words or providers.</p>
      )}
      {results.length > 0 && (
        <ul className="track-list">
          {results.map((hit) => (
            <li key={`${hit.provider}:${hit.external_id}`} className="track-card">
              <strong>{displayHit(hit)}</strong>
              <p>
                <small>
                  via {hit.provider}
                  {hit.attribution ? ` · ${hit.attribution}` : ""}
                </small>
              </p>
              {hit.source_url && (
                <p>
                  <a href={hit.source_url} target="_blank" rel="noreferrer">
                    source page
                  </a>
                </p>
              )}
              {(hit.warnings ?? []).map((warning, index) => <p key={index}>{warning}</p>)}
              <ImportControl
                hit={hit}
                jobId={importJobs[`${hit.provider}:${hit.external_id}`] ?? null}
                onImport={() => void importHit(hit)}
              />
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}

function ImportControl({
  hit,
  jobId,
  onImport,
}: {
  hit: SearchHit;
  jobId: string | null;
  onImport: () => void;
}) {
  const { job } = useJob(jobId);
  if (!jobId) {
    return (
      <button type="button" onClick={onImport}>
        Import “{hit.title ?? hit.external_id}” to the library
      </button>
    );
  }
  if (!job || (job.status !== "succeeded" && job.status !== "failed")) {
    return (
      <p role="status">
        Importing… {job ? `${Math.round(job.progress * 100)}%` : ""}
        {job?.wait_reason ? ` (${job.wait_reason})` : ""}
      </p>
    );
  }
  if (job.status === "failed") {
    return <ErrorNotice message={`Import failed: ${job.error ?? "unknown error"}`} />;
  }
  const trackId = (job.result as { track_id?: string } | null)?.track_id;
  const reused = (job.result as { reused?: boolean } | null)?.reused;
  const warnings = (job.result as { warnings?: string[] } | null)?.warnings ?? [];
  return (
    <div role="status">
      Imported{reused ? " (already in the library)" : ""}.{" "}
      {trackId && <Link to={`/tracks/${trackId}`}>Open the track</Link>}
      {warnings.map((warning, index) => <p key={index}>{warning}</p>)}
    </div>
  );
}
