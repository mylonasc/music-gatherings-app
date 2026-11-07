import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, post } from "../../lib/api-client";
import type { CrewTrackListItem, TrackSuggest } from "../../lib/api-types";
import { ErrorNotice, Field } from "../../components/ui";

const PIANO_OPTIONS = ["unknown", "suggested", "not_suggested"] as const;

export function SuggestTrackForm({
  crewId,
  onCreated,
  initialOpen = false,
}: {
  crewId: string;
  onCreated: (item: CrewTrackListItem) => void;
  initialOpen?: boolean;
}) {
  const [open, setOpen] = useState(initialOpen);
  const lock = useRef(false);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [description, setDescription] = useState("");
  const [genres, setGenres] = useState("");
  const [notes, setNotes] = useState("");
  const [piano, setPiano] = useState<string>("unknown");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    lock.current = true;
    setFormError(null);
    setSubmitting(true);
    try {
      const body: TrackSuggest = {
        title: title.trim() || null,
        artist: artist.trim() || null,
        description: description.trim() || null,
        genres: genres.split(",").map((g) => g.trim()).filter(Boolean),
        versions: [],
        notes: notes.trim() || null,
        piano_suitability: piano,
      };
      const created = await post<CrewTrackListItem>(`/api/v1/crews/${crewId}/tracks`, body);
      onCreated(created);
      setOpen(false);
      setTitle("");
      setArtist("");
      setDescription("");
      setGenres("");
      setNotes("");
      setPiano("unknown");
    } catch (err: unknown) {
      setFormError(err instanceof ApiError ? err.message : "Could not suggest the track.");
    } finally {
      lock.current = false;
      setSubmitting(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}>
        Suggest a track
      </button>
    );
  }

  return (
    <form className="suggest-form" onSubmit={onSubmit} noValidate aria-label="Suggest a track">
      <h3>Suggest a track</h3>
      {formError && <ErrorNotice message={formError} />}
      <Field id="suggest-title" label="Title (optional)">
        <input
          id="suggest-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={256}
        />
      </Field>
      <Field id="suggest-artist" label="Artist (optional)">
        <input
          id="suggest-artist"
          value={artist}
          onChange={(e) => setArtist(e.target.value)}
          maxLength={256}
        />
      </Field>
      <Field id="suggest-genres" label="Genres (comma-separated, optional)">
        <input
          id="suggest-genres"
          value={genres}
          onChange={(e) => setGenres(e.target.value)}
          placeholder="Rock, Folk"
        />
      </Field>
      <Field id="suggest-description" label="Description (optional)">
        <textarea
          id="suggest-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={2}
        />
      </Field>
      <Field id="suggest-notes" label="Notes for the crew (optional)">
        <textarea
          id="suggest-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
        />
      </Field>
      <Field id="suggest-piano" label="Piano suitability">
        <select id="suggest-piano" value={piano} onChange={(e) => setPiano(e.target.value)}>
          {PIANO_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </Field>
      <div className="form-actions">
        <button type="submit" disabled={submitting}>
          {submitting ? "Suggesting…" : "Suggest"}
        </button>{" "}
        <button type="button" disabled={submitting} onClick={() => setOpen(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
