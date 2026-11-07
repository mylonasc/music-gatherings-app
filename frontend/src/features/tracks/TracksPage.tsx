import { useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorNotice, Loading, Page } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import { sanitizeSnippet } from "../../lib/snippet";
import type { CrewTrackList, SearchResponse } from "../../lib/api-types";
import { useAuth } from "../auth/AuthContext";
import { SuggestTrackForm } from "./SuggestTrackForm";
import { TrackCard, displayTitle } from "./TrackCard";
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
      <div className="library-intro"><div><h3>The soundtrack to your next gathering.</h3>
      <p>Find a favourite, cast your vote, or bring something new to the crew.</p></div>
      {user && <span className="badge">{crews?.[0]?.name ?? user.username}</span>}</div>
      {crewsLoading && <Loading label="Loading your crew…" />}
      {crewsError && <ErrorNotice message={crewsError} />}
      {!crewsLoading && !crewsError && crews?.length === 0 && (
        <p role="status">You are not in a crew yet. Ask an admin to approve your access.</p>
      )}
      {crewId && (
        <>
          <form
            role="search"
            aria-label="Filter and search tracks"
            onSubmit={(e) => {
              e.preventDefault();
              setSearchNonce((n) => n + 1);
              reload();
            }}
          >
            <label htmlFor="track-search">Search the library</label>
            <input
              id="track-search"
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Title, artist, or lyrics"
            />
            <label htmlFor="genre-filter">Genre</label>
            <input
              id="genre-filter"
              value={genreFilter}
              onChange={(e) => setGenreFilter(e.target.value)}
              placeholder="Rock"
            />
            <label htmlFor="piano-filter">
              <input
                id="piano-filter"
                type="checkbox"
                checked={pianoOnly}
                onChange={(e) => setPianoOnly(e.target.checked)}
              />{" "}
              Piano-friendly only
            </label>
            <button type="submit">Apply</button>
          </form>
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
          {tracks.items.map((item) => <TrackCard key={`${crewId}:${listParams}:${item.crew_track_id}`} item={item} crewId={crewId} />)}
        </ul>
      )}
    </Page>
  );
}
