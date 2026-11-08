import { useEffect, useRef, useState } from "react";
import { del } from "../../lib/api-client";
import { ErrorNotice } from "../../components/ui";
import { BinIcon } from "../../components/icons";

/** Delete the authorized crew listing, never silently purge shared music. */
export function DeleteTrackControl({ crewId, crewTrackId, title, onDeleted }: {
  crewId: string; crewTrackId: string; title: string; onDeleted: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lock = useRef(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const cancel = useRef<HTMLButtonElement>(null);
  const wasConfirming = useRef(false);
  useEffect(() => {
    if (confirming) cancel.current?.focus();
    else if (wasConfirming.current) trigger.current?.focus();
    wasConfirming.current = confirming;
  }, [confirming]);
  async function remove() {
    if (lock.current) return;
    lock.current = true; setPending(true); setError(null);
    try {
      await del(`/api/v1/crews/${crewId}/tracks/${crewTrackId}`);
      onDeleted();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not delete this track from the crew."); }
    finally { lock.current = false; setPending(false); }
  }
  return <div className="track-delete">
    <button ref={trigger} type="button" className="danger-action delete-trigger" aria-label={`Delete track: ${title}`} title={`Delete ${title} from this crew`} disabled={pending || confirming} onClick={() => { setConfirming(true); setError(null); }}><BinIcon /></button>
    {confirming && <div className="delete-confirmation" role="group" aria-label={`Delete ${title} from this crew`} aria-busy={pending}>
      <p><strong>Delete “{title}” from this crew?</strong></p>
      <p>This removes the crew’s listing and its votes. It does not permanently erase music files or remove the track from other crews.</p>
      {error && <ErrorNotice message={error} />}
      <div className="form-actions"><button ref={cancel} type="button" disabled={pending} onClick={() => setConfirming(false)}>Cancel deletion</button>
        <button type="button" className="danger-action" disabled={pending} onClick={() => void remove()}>{pending ? "Deleting…" : "Delete from crew"}</button></div>
    </div>}
  </div>;
}
