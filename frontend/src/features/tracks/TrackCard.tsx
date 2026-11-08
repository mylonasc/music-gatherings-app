import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../../components/ui";
import type { CrewTrackListItem } from "../../lib/api-types";
import { UpvoteToggle } from "./UpvoteToggle";
import { DeleteTrackControl } from "./DeleteTrackControl";

export function displayTitle(title: string | null, artist: string | null): string {
  return title && artist ? `${title} — ${artist}` : title ?? artist ?? "Untitled track";
}

export function TrackCard({ item, crewId, onDeleted }: { item: CrewTrackListItem; crewId: string; onDeleted: () => void }) {
  const [vote, setVote] = useState({ count: item.upvote_count ?? 0, myVote: item.my_vote });
  return <li className="track-card library-card">
    <div className="library-summary">
      <Link className="library-track-title" to={`/tracks/${item.track_id}`}><strong>{displayTitle(item.title, item.artist)}</strong></Link>
      <div className="library-meta">
        {item.requester && <span>by {item.requester}</span>}
        {item.genres.length > 0 && <span>{item.genres.join(", ")}</span>}
        <span>{item.version_count} version{item.version_count === 1 ? "" : "s"}</span>
      </div>
      {(item.artifact_kinds.length > 0 || item.piano_suitability === "suggested") && <div className="material-badges" role="group" aria-label="Available materials">
        {item.artifact_kinds.map((kind) => <Badge key={kind}>{kind.replaceAll("_", " ")}</Badge>)}
        {item.piano_suitability === "suggested" && <Badge>piano-friendly</Badge>}
      </div>}
    </div>
    <UpvoteToggle crewId={crewId} crewTrackId={item.crew_track_id} count={vote.count} myVote={vote.myVote}
      onChanged={(count, myVote) => setVote({ count, myVote })} />
    {item.can_remove && <DeleteTrackControl crewId={crewId} crewTrackId={item.crew_track_id} title={item.title ?? item.artist ?? "Untitled track"} onDeleted={onDeleted} />}
  </li>;
}
