import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import { sanitizeSnippet } from "../../lib/snippet";
import type { CrewTrackList, SearchResponse } from "../../lib/api-types";
import { useAuth } from "../auth/AuthContext";
import { SuggestTrackForm } from "./SuggestTrackForm";
import { TrackCard, displayTitle } from "./TrackCard";
import { TrackFilters } from "./TrackFilters";
import "./tracks.css";

export function TracksPage() {
  const { user } = useAuth();
  const { data: crews, loading: crewsLoading, error: crewsError } = useGet<{ id: string; name: string }[]>(
    "/api/v1/crews",
  );
  const crewId = crews && crews.length > 0 ? crews[0].id : null;
  const [genreFilter, setGenreFilter] = useState("");
  const [pianoOnly, setPianoOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchNonce, setSearchNonce] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const listParams = new URLSearchParams({ limit: "50" });
  if (genreFilter.trim()) listParams.set("genre", genreFilter.trim());
  if (pianoOnly) listParams.set("piano_suggested", "true");
  const {
    data: tracks,
    error: tracksError,
    loading: tracksLoading,
    reload,
  } = useGet<CrewTrackList>(crewId ? `/api/v1/crews/${crewId}/tracks?${listParams}` : null);

  const {
    data: searchResults,
    error: searchError,
    loading: searchLoading,
  } = useGet<SearchResponse>(
    crewId && searchQuery.trim()
      ? `/api/v1/search/local?q=${encodeURIComponent(searchQuery.trim())}&limit=20&nonce=${searchNonce}`
      : null,
  );

  return (
    <Page title="Jam tracks">
      {notice && <p className="feedback" role="status">{notice}</p>}
      <div className="library-intro"><div><h3>The soundtrack to your next gathering.</h3>
      <p>Find a favourite, cast your vote, or bring something new to the crew.</p></div>
      {user && <span className="badge">{crews?.[0]?.name ?? user.username}</span>}</div>
      <p><Link className="action-link" to="/add">+ Bring a song</Link></p>
      {crewsLoading && <Loading label="Loading your crew…" />}
      {crewsError && <ErrorNotice message={crewsError} />}
      {!crewsLoading && !crewsError && crews?.length === 0 && (
        <p role="status">You are not in a crew yet. Ask an admin to approve your access.</p>
      )}
      {crewId && (
        <>
          <TrackFilters query={searchQuery} genre={genreFilter} pianoOnly={pianoOnly} onQuery={setSearchQuery} onGenre={setGenreFilter} onPiano={setPianoOnly} onApply={() => { setSearchNonce((n) => n + 1); reload(); }} />
          <SuggestTrackForm
            crewId={crewId}
            onCreated={() => {
              setSearchQuery("");
              reload();
            }}
          />
        </>
      )}
      {tracksLoading && <Loading label="Loading tracks…" />}
      {tracksError && <ErrorNotice message={tracksError} onRetry={reload} />}
      {searchLoading && <Loading label="Searching…" />}
      {searchError && <ErrorNotice message={searchError} />}
      {searchResults && searchQuery.trim() && (
        <section aria-label="Library search results">
          <h3>
            {searchResults.total} result{searchResults.total === 1 ? "" : "s"} for “{searchQuery.trim()}”
          </h3>
          {(searchResults.items ?? []).length === 0 && <p role="status">No matches. Try fewer words.</p>}
          <ul className="track-list">
            {(searchResults.items ?? []).map((hit) => (
              <li key={hit.track_id} className="track-card">
                <Link to={`/tracks/${hit.track_id}`}>
                  <strong>{displayTitle(hit.title, hit.artist)}</strong>
                </Link>
                <p>
                  <small>
                    matched by {hit.source} · score {(hit.score ?? 0).toFixed(2)}
                  </small>
                </p>
                {hit.snippet && (
                  <p>
                    <small dangerouslySetInnerHTML={{ __html: sanitizeSnippet(hit.snippet) }} />
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
      {tracks && !searchQuery.trim() && tracks.items.length === 0 && (
        <EmptyState title="No tracks yet.">Suggest the first song for the next jam.</EmptyState>
      )}
      {tracks && crewId && !searchQuery.trim() && tracks.items.length > 0 && (
        <ul className="track-list library-grid">
          {tracks.items.map((item) => <TrackCard key={`${crewId}:${listParams}:${item.crew_track_id}`} item={item} crewId={crewId} onDeleted={() => { setNotice("Track deleted from this crew."); reload(); document.getElementById("page-title")?.focus(); }} />)}
        </ul>
      )}
    </Page>
  );
}
