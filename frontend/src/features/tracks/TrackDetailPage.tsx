import { Link, useParams } from "react-router-dom";
import { ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import type { ArtifactOut, TrackDetail } from "../../lib/api-types";

function artifactLabel(kind: string): string {
  return kind.replaceAll("_", " ");
}

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

  return (
    <Page title={title}>
      <p>
        <Link to="/">← Jam tracks</Link>
      </p>
      {subtitle && <p>{subtitle}</p>}
      {data.description && <p>{data.description}</p>}
      {data.genres.length > 0 && <p>Genres: {data.genres.join(", ")}</p>}
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
      {data.versions.map((version) => (
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
