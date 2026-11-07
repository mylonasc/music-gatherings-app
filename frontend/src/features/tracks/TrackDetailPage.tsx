import { Link, useParams } from "react-router-dom";
import { Badge, ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import type { TrackDetail } from "../../lib/api-types";
import { MaterialForm } from "../adding/MaterialForm";
import { Representations } from "./Representations";
import { TrackVersions } from "./TrackVersions";
import "./tracks.css";

export function TrackDetailPage() {
  const { trackId } = useParams<{ trackId: string }>();
  const { data, error, loading, reload } = useGet<TrackDetail>(trackId ? `/api/v1/tracks/${trackId}` : null);
  if (loading) return <Loading label="Loading track…" />;
  if (error || !data) return <Page title="Track"><ErrorNotice message={error ?? "Track not found."} onRetry={reload} /><p><Link to="/">Back to jam tracks</Link></p></Page>;
  const title = data.title ?? data.artist ?? "Untitled track";
  return <Page title={title}>
    <p><Link to="/">← Jam tracks</Link></p>
    {data.title && data.artist && <p className="track-artist">{data.title} — {data.artist}</p>}
    {data.description && <p>{data.description}</p>}
    <div className="material-badges">{data.genres.map((genre) => <Badge key={genre}>{genre}</Badge>)}</div>
    <div className="crew-entries">{data.crew_entries.map((entry) => <section key={entry.crew_track_id} aria-label={`${entry.crew_name} entry`}>
      <h3>{entry.crew_name} · votes {entry.vote_score}</h3>
      {entry.requester && <p>Suggested by {entry.requester}</p>}{entry.notes && <p>{entry.notes}</p>}
    </section>)}</div>
    {trackId && <Representations key={trackId} trackId={trackId} versions={data.versions} />}
    <h3>Versions and materials</h3>
    <MaterialForm key={data.id} trackId={data.id} versions={data.versions} onSaved={reload} />
    {!data.versions.length && <p role="status">No versions yet.</p>}
    <TrackVersions versions={data.versions} />
  </Page>;
}
