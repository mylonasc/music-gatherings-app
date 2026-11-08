import { useRef, useState } from "react";
import { ApiError, del, put } from "../../lib/api-client";
import type { CrewTrackListItem } from "../../lib/api-types";
import { ThumbUpIcon } from "../../components/icons";

export function UpvoteToggle({ crewId, crewTrackId, count, myVote, onChanged }: {
  crewId: string; crewTrackId: string; count: number; myVote: number | null;
  onChanged: (count: number, myVote: number | null) => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const liked = myVote === 1;
  async function toggle() {
    if (lock.current) return;
    lock.current = true; setPending(true); setError(null);
    try {
      const path = `/api/v1/crews/${crewId}/tracks/${crewTrackId}/vote`;
      if (liked) { await del(path); onChanged(Math.max(0, count - 1), null); }
      else {
        const updated = await put<CrewTrackListItem>(path, { value: 1 });
        onChanged(updated.upvote_count ?? 0, updated.my_vote);
      }
    } catch (err) { setError(err instanceof ApiError ? err.message : "Could not update your thumbs up."); }
    finally { lock.current = false; setPending(false); }
  }
  return <div className="upvote-control">
    <button className="upvote-toggle" type="button" disabled={pending} aria-pressed={liked}
      aria-label={liked ? "Remove thumbs up" : "Give thumbs up"}
      title={liked ? "Remove your thumbs up" : "Give this track a thumbs up"} onClick={() => void toggle()}>
      <ThumbUpIcon /><span aria-hidden="true">{count}</span>
    </button>
    <span className="sr-only" role="status">{count} thumbs up</span>
    {error && <span role="alert" className="field-error">{error}</span>}
  </div>;
}
