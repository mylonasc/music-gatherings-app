import { Badge } from "../../components/ui";
import { ImportControl } from "./ImportControl";
import type { SearchHit } from "./types";

export function SearchResultCard({ hit, crewId }: { hit: SearchHit; crewId: string }) {
  return <li className="track-card">
    <p className="eyebrow">via {hit.provider}</p><h3>{hit.title ?? "Untitled"}{hit.artist ? ` — ${hit.artist}` : ""}</h3>
    <div className="material-badges">{hit.artifact_types.map((kind) => <Badge key={kind}>{kind.replaceAll("_", " ")}</Badge>)}</div>
    {hit.attribution && <p><small>{hit.attribution}</small></p>}
    {hit.source_url && <p><a href={hit.source_url} target="_blank" rel="noreferrer">source page</a></p>}
    {hit.warnings?.map((warning, i) => <p key={i} role="note">{warning}</p>)}
    <ImportControl hit={hit} crewId={crewId} />
  </li>;
}
