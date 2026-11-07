import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { post } from "../../lib/api-client";
import type { JobOut, ProviderOption } from "../../lib/api-types";
import { useGet } from "../../lib/use-api";
import { useJob } from "../../lib/use-job";
import { EmptyState, ErrorNotice, Field, Loading, Page } from "../../components/ui";
import { SearchResultCard } from "./SearchResultCard";
import type { SearchHit } from "./types";

export function OnlineSearchPage() {
  const { data: crews, error: crewsError } = useGet<{ id: string; name: string }[]>("/api/v1/crews");
  const crewId = crews?.[0]?.id;
  return <Page title="Online search"><p>Find your next favourite. Discovery never changes your library; importing is a separate, explicit step.</p>
    {crewsError && <ErrorNotice message={crewsError} />}
    {crews && !crewId && <EmptyState title="Join a crew before searching online." />}
    {crewId && <Discovery key={crewId} crewId={crewId} />}
  </Page>;
}

function Discovery({ crewId }: { crewId: string }) {
  const { data: options, loading, error, reload } = useGet<ProviderOption[]>("/api/v1/providers");
  const [query, setQuery] = useState("");
  const [providers, setProviders] = useState<string[]>(["fake"]);
  const [jobId, setJobId] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const lock = useRef(false);
  const { job, error: jobError } = useJob(jobId);
  async function search(event: FormEvent) {
    event.preventDefault();
    const selected = providers.filter((id) => options?.some((p) => p.provider === id && p.available && p.supports_search));
    if (lock.current || !query.trim() || !selected.length) return;
    lock.current = true; setStarting(true); setSubmitError(null); setJobId(null);
    try { const started = await post<JobOut>("/api/v1/search/online", { crew_id: crewId, query: query.trim(), providers: selected }); setJobId(started.id); }
    catch (err) { setSubmitError(err instanceof Error ? err.message : "Search failed to start."); }
    finally { lock.current = false; setStarting(false); }
  }
  const results = job?.status === "succeeded" ? Object.entries((job.result as { results?: Record<string, SearchHit[]> })?.results ?? {}).flatMap(([provider, hits]) => hits.map((hit) => ({ ...hit, provider }))) : [];
  return <>
    {loading && <Loading label="Loading providers…" />}{error && <ErrorNotice message={error} onRetry={reload} />}
    <form onSubmit={search} aria-label="Online provider search" className="surface-panel">
      {submitError && <ErrorNotice message={submitError} />}
      <Field id="online-query" label="Song or artist"><input id="online-query" type="search" maxLength={200} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Title or artist" /></Field>
      <fieldset><legend>Providers</legend>{options?.map((p) => <div key={p.provider}>
        <label htmlFor={`provider-${p.provider}`}><input id={`provider-${p.provider}`} type="checkbox" disabled={!p.available || !p.supports_search} checked={providers.includes(p.provider)} onChange={(e) => setProviders((prev) => e.target.checked ? [...prev, p.provider] : prev.filter((id) => id !== p.provider))} />{p.provider === "lrclib" ? "LRCLIB" : p.provider.replaceAll("_", " ")}</label>
        <small className="provider-note">{!p.available || !p.supports_search ? "Unavailable for discovery" : p.storage_note || (p.allows_storage ? "Local imports supported" : "Reference-only")}</small>
      </div>)}</fieldset>
      <button type="submit" disabled={starting || loading || !query.trim() || !providers.some((id) => options?.some((p) => p.provider === id && p.available && p.supports_search))}>{starting ? "Starting…" : "Search online"}</button>
    </form>
    {(jobError || job?.status === "failed" || job?.status === "cancelled") && <ErrorNotice message={jobError ?? `Search ${job?.status}: ${job?.error ?? "No results"}`} />}
    {job && !["succeeded", "failed", "cancelled"].includes(job.status) && <p className="feedback" role="status">Searching… {Math.round(job.progress * 100)}% {job.wait_reason}</p>}
    {job?.status === "succeeded" && !results.length && <EmptyState title="No provider results.">Try different words or providers.</EmptyState>}
    {!!results.length && <ul className="track-list">{results.map((hit) => <SearchResultCard key={`${crewId}:${hit.provider}:${hit.external_id}`} hit={hit} crewId={crewId} />)}</ul>}
  </>;
}
