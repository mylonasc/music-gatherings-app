import { Link } from "react-router-dom";
import { ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import type { CrewTrackList } from "../../lib/api-types";
import { useAuth } from "../auth/AuthContext";

function displayTitle(title: string | null, artist: string | null): string {
  if (title && artist) return `${title} — ${artist}`;
  return title ?? artist ?? "Untitled track";
}

export function TracksPage() {
  const { user } = useAuth();
  const {
    data: crews,
    loading: crewsLoading,
    error: crewsError,
  } = useGet<{ id: string; name: string }[]>("/api/v1/crews");
  const crewId = crews && crews.length > 0 ? crews[0].id : null;
  const {
    data: tracks,
    error: tracksError,
    loading: tracksLoading,
    reload,
  } = useGet<CrewTrackList>(crewId ? `/api/v1/crews/${crewId}/tracks?limit=50` : null);

  return (
    <Page title="Jam tracks">
      {user && <p>Signed in as {user.username}.</p>}
      {crewsLoading && <Loading label="Loading your crew…" />}
      {crewsError && <ErrorNotice message={crewsError} />}
      {!crewsLoading && !crewsError && crews?.length === 0 && (
        <p role="status">You are not in a crew yet. Ask an admin to approve your access.</p>
      )}
      {tracksLoading && <Loading label="Loading tracks…" />}
      {tracksError && <ErrorNotice message={tracksError} onRetry={reload} />}
      {tracks && tracks.items.length === 0 && (
        <p role="status">
          No tracks yet. Suggest the first song for the next jam (coming in the crew view).
        </p>
      )}
      {tracks && tracks.items.length > 0 && (
        <ul className="track-list">
          {tracks.items.map((item) => (
            <li key={item.crew_track_id} className="track-card">
              <Link to={`/tracks/${item.track_id}`}>
                <strong>{displayTitle(item.title, item.artist)}</strong>
              </Link>
              <dl>
                {item.requester && (
                  <>
                    <dt>Suggested by</dt>
                    <dd>{item.requester}</dd>
                  </>
                )}
                {item.genres.length > 0 && (
                  <>
                    <dt>Genres</dt>
                    <dd>{item.genres.join(", ")}</dd>
                  </>
                )}
                <dt>Votes</dt>
                <dd>
                  {item.vote_score}
                  {item.my_vote !== null && item.my_vote !== undefined
                    ? ` (you voted ${item.my_vote > 0 ? "+1" : "−1"})`
                    : ""}
                  {item.piano_suitability === "suggested" ? " · piano-friendly" : ""}
                </dd>
                {item.artifact_kinds.length > 0 && (
                  <>
                    <dt>Available</dt>
                    <dd>{item.artifact_kinds.join(", ").replaceAll("_", " ")}</dd>
                  </>
                )}
              </dl>
            </li>
          ))}
        </ul>
      )}
    </Page>
  );
}
