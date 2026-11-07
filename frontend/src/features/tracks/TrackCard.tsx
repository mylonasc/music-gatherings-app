import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui";
import type { CrewTrackListItem } from "../../lib/api-types";
import { VoteButtons } from "./VoteButtons";

export function displayTitle(title: string | null, artist: string | null): string {
  return title && artist ? `${title} — ${artist}` : title ?? artist ?? "Untitled track";
}

export function TrackCard({ item, crewId }: { item: CrewTrackListItem; crewId: string }) {
  const [vote, setVote] = useState({ score: item.vote_score, myVote: item.my_vote });
  return <li className="track-card library-card">
    <div className="track-card-heading"><span className="song-mark" aria-hidden="true">♫</span>
      <div><p className="eyebrow">{item.version_count} version{item.version_count === 1 ? "" : "s"}</p>
        <Link to={`/tracks/${item.track_id}`}><strong>{displayTitle(item.title, item.artist)}</strong></Link>
      </div>
    </div>
    <dl>
      {item.requester && <><dt>Suggested by</dt><dd>{item.requester}</dd></>}
      {item.genres.length > 0 && <><dt>Genres</dt><dd>{item.genres.join(", ")}</dd></>}
    </dl>
    <div className="material-badges" role="group" aria-label="Available materials">
      {item.artifact_kinds.map((kind) => <Badge key={kind}>{kind.replaceAll("_", " ")}</Badge>)}
      {item.piano_suitability === "suggested" && <Badge>piano-friendly</Badge>}
    </div>
    <VoteButtons crewId={crewId} crewTrackId={item.crew_track_id} score={vote.score} myVote={vote.myVote}
      onChanged={(score, myVote) => setVote({ score, myVote })} />
  </li>;
}
