import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import { ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet, useText } from "../../lib/use-api";
import type { ArtifactOut, RepresentationResponse, TrackDetail, VersionDetailOut } from "../../lib/api-types";

function artifactLabel(kind: string): string {
  return kind.replaceAll("_", " ");
}

type ViewContext = "audience" | "guitar" | "piano";

export function TrackDetailPage() {
  const { trackId } = useParams<{ trackId: string }>();
  const { data, error, loading, reload } = useGet<TrackDetail>(
    trackId ? `/api/v1/tracks/${trackId}` : null,
  );

  if (loading) return <Loading label="Loading track…" />;
  if (error || !data)
    return (
      <Page title="Track">
        <ErrorNotice message={error ?? "Track not found."} onRetry={reload} />
        <p>
          <Link to="/">Back to jam tracks</Link>
        </p>
      </Page>
    );

  const title = data.title ?? data.artist ?? "Untitled track";
  const subtitle = data.title && data.artist ? `${data.title} — ${data.artist}` : null;
  const musicalKeys = Array.from(
    new Set(data.versions.map((v) => v.musical_key).filter((k): k is string => Boolean(k))),
  );

  return (
    <Page title={title}>
      <p>
        <Link to="/">← Jam tracks</Link>
      </p>
      {subtitle && <p>{subtitle}</p>}
      {data.description && <p>{data.description}</p>}
      {data.genres.length > 0 && <p>Genres: {data.genres.join(", ")}</p>}
      {musicalKeys.length > 0 && <p>Keys: {musicalKeys.join(", ")}</p>}
      {data.crew_entries.map((entry) => (
        <section key={entry.crew_track_id} aria-label={`${entry.crew_name} entry`}>
          <h3>
            {entry.crew_name} · votes {entry.vote_score}
          </h3>
          {entry.requester && <p>Suggested by {entry.requester}</p>}
          {entry.notes && <p>{entry.notes}</p>}
        </section>
      ))}
      <h3>Versions and materials</h3>
      {data.versions.length === 0 && <p role="status">No versions yet.</p>}
      {trackId && <Representations trackId={trackId} />}
      {data.versions.map((version: VersionDetailOut) => (
        <section key={version.id} aria-label={version.label ?? "Version"}>
          <h4>{version.label ?? "Version"}</h4>
          {version.musical_key && <p>Key: {version.musical_key}</p>}
          {version.notes && <p>{version.notes}</p>}
          {(version.artifacts ?? []).length === 0 && <p>No materials attached yet.</p>}
          <ul>
            {(version.artifacts ?? []).map((artifact: ArtifactOut) => (
              <li key={artifact.id}>
                {artifactLabel(artifact.kind)} ({artifact.mime_type})
                {artifact.is_external && artifact.external_url ? (
                  <>
                    {" — "}
                    <a href={artifact.external_url} target="_blank" rel="noreferrer">
                      open external reference
                    </a>
                  </>
                ) : (
                  <>
                    {" — "}
                    <a href={`/api/v1/artifacts/${artifact.id}/content`}>
                      download{artifact.file_name ? ` ${artifact.file_name}` : ""}
                    </a>
                  </>
                )}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </Page>
  );
}

function Representations({ trackId }: { trackId: string }) {
  const [context, setContext] = useState<ViewContext>("audience");
  const { data, error, loading } = useGet<RepresentationResponse>(
    `/api/v1/tracks/${trackId}/representations?context=${context}`,
  );

  return (
    <section aria-label="Representations">
      <h3>Views</h3>
      <div role="group" aria-label="Choose your view">
        {(["audience", "guitar", "piano"] as const).map((option) => (
          <label key={option} htmlFor={`context-${option}`}>
            <input
              id={`context-${option}`}
              type="radio"
              name="view-context"
              value={option}
              checked={context === option}
              onChange={() => setContext(option)}
            />{" "}
            {option}
          </label>
        ))}
      </div>
      {loading && <Loading label="Loading view…" />}
      {error && <ErrorNotice message={error} />}
      {data && (data.items ?? []).length === 0 && (
        <p role="status">Nothing available for the {context} view yet.</p>
      )}
      {data && (
        <ul className="track-list">
          {(data.items ?? []).map((item) => (
            <li key={item.artifact.id} className="track-card">
              <strong>{artifactLabel(item.artifact.kind)}</strong>{" "}
              <small>
                ({item.artifact.mime_type}
                {item.derived ? ", derived" : ", original"}
                {item.source_provider ? ` via ${item.source_provider}` : ""})
              </small>
              {item.attribution && (
                <p>
                  <small>{item.attribution}</small>
                </p>
              )}
              {(item.warnings ?? []).map((warning, index) => (
                <p key={index} role="note">
                  <small>Note: {warning}</small>
                </p>
              ))}
              <DocPanel artifact={item.artifact} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DocPanel({ artifact }: { artifact: ArtifactOut }) {
  const isText = artifact.mime_type === "text/plain" || artifact.mime_type === "application/x-lrc";
  const { data, error, loading } = useText(
    artifact.is_external || (!isText && artifact.mime_type !== "text/html")
      ? null
      : `/api/v1/artifacts/${artifact.id}/content`,
  );
  if (artifact.is_external && artifact.external_url) {
    return (
      <p>
        <a href={artifact.external_url} target="_blank" rel="noreferrer">
          open external reference
        </a>
      </p>
    );
  }
  if (!isText && artifact.mime_type !== "text/html") {
    return null;
  }
  if (loading) return <Loading label="Loading document…" />;
  if (error || data === null) return <ErrorNotice message={error ?? "Document unavailable."} />;
  if (isText) {
    return (
      <pre className="doc-panel" role="region" aria-label={`${artifactLabel(artifact.kind)} document`} tabIndex={0}>
        {data}
      </pre>
    );
  }
  // The HTML is rendered by our own processor with escaping; it is never
  // raw provider content. The panel scrolls internally on narrow screens and
  // is keyboard-focusable so scrollable content stays operable (axe:
  // scrollable-region-focusable).
  return (
    <div
      className="doc-panel"
      role="region"
      aria-label={`${artifactLabel(artifact.kind)} document`}
      tabIndex={0}
      dangerouslySetInnerHTML={{ __html: data }}
    />
  );
}
