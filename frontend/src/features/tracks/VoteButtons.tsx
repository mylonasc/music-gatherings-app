import { useState } from "react";
import { ApiError, del, put } from "../../lib/api-client";
import type { CrewTrackListItem } from "../../lib/api-types";

export function VoteButtons({
  crewId,
  crewTrackId,
  score,
  myVote,
  onChanged,
}: {
  crewId: string;
  crewTrackId: string;
  score: number;
  myVote: number | null;
  onChanged: (score: number, myVote: number | null) => void;
}) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function vote(value: 1 | -1) {
    setPending(true);
    setError(null);
    try {
      const updated = await put<CrewTrackListItem>(
        `/api/v1/crews/${crewId}/tracks/${crewTrackId}/vote`,
        { value },
      );
      onChanged(updated.vote_score, updated.my_vote);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Vote failed.");
    } finally {
      setPending(false);
    }
  }

  async function clear() {
    setPending(true);
    setError(null);
    try {
      await del(`/api/v1/crews/${crewId}/tracks/${crewTrackId}/vote`);
      onChanged(score - (myVote ?? 0), null);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "Vote failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="votes" role="group" aria-label="Votes">
      <span aria-live="polite">Votes {score}</span>{" "}
      <button type="button" disabled={pending} onClick={() => void vote(1)} aria-pressed={myVote === 1}>
        +1
      </button>{" "}
      <button type="button" disabled={pending} onClick={() => void vote(-1)} aria-pressed={myVote === -1}>
        −1
      </button>{" "}
      {myVote !== null && (
        <button type="button" disabled={pending} onClick={() => void clear()}>
          Clear
        </button>
      )}
      {error && (
        <span role="alert" className="field-error">
          {error}
        </span>
      )}
    </div>
  );
}
