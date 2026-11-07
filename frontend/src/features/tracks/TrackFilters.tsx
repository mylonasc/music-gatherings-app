import type { FormEvent } from "react";
import { Field } from "../../components/ui";

interface Props {
  query: string; genre: string; pianoOnly: boolean;
  onQuery: (value: string) => void; onGenre: (value: string) => void;
  onPiano: (value: boolean) => void; onApply: () => void;
}
export function TrackFilters({ query, genre, pianoOnly, onQuery, onGenre, onPiano, onApply }: Props) {
  function apply(event: FormEvent) { event.preventDefault(); onApply(); }
  return <form role="search" aria-label="Filter and search tracks" className="library-filters" onSubmit={apply}>
    <Field id="track-search" label="Search the library"><input id="track-search" type="search" value={query} onChange={(e) => onQuery(e.target.value)} placeholder="Title, artist, or lyrics" /></Field>
    <details><summary>Filters{genre || pianoOnly ? " · active" : ""}</summary>
      <Field id="genre-filter" label="Genre"><input id="genre-filter" value={genre} onChange={(e) => onGenre(e.target.value)} placeholder="Rock" /></Field>
      <label htmlFor="piano-filter"><input id="piano-filter" type="checkbox" checked={pianoOnly} onChange={(e) => onPiano(e.target.checked)} />Piano-friendly only</label>
    </details>
    <button type="submit">Apply</button>
  </form>;
}
