import { useState } from "react";
import { Badge, EmptyState, ErrorNotice, Field, Loading } from "../../components/ui";
import { useGet } from "../../lib/use-api";
import type { RepresentationResponse, VersionDetailOut } from "../../lib/api-types";
import { DocumentViewer } from "./viewers/DocumentViewer";

type ViewContext = "audience" | "guitar" | "piano";
const contexts: readonly ViewContext[] = ["audience", "guitar", "piano"];

export function Representations({ trackId, versions }: { trackId: string; versions: VersionDetailOut[] }) {
  const [context, setContext] = useState<ViewContext>("audience");
  const [versionId, setVersionId] = useState("");
  const { data, error, loading, reload } = useGet<RepresentationResponse>(`/api/v1/tracks/${trackId}/representations?context=${context}`);
  const items = data?.items?.filter((item) => !versionId || item.artifact.track_version_id === versionId) ?? [];
  return <section className="reading-workspace" aria-label="Representations">
    <div className="workspace-heading"><div><p className="eyebrow">Make it your own</p><h3>Views</h3></div><Badge>Music stand</Badge></div>
    <div className="workspace-toolbar">
      <div role="group" aria-label="Choose your view">{contexts.map((option) => <label key={option} htmlFor={`context-${option}`}>
        <input id={`context-${option}`} type="radio" name="view-context" checked={context === option} onChange={() => setContext(option)} />{option}
      </label>)}</div>
      {versions.length > 1 && <Field id="reading-version" label="Reading version"><select id="reading-version" value={versionId} onChange={(e) => setVersionId(e.target.value)}><option value="">All versions</option>{versions.map((version) => <option key={version.id} value={version.id}>{version.label ?? "Version"}</option>)}</select></Field>}
    </div>
    {loading && <Loading label="Loading view…" />}{error && <ErrorNotice message={error} onRetry={reload} />}
    {data && !items.length && <EmptyState title={`Nothing available for the ${context} view yet.`}>Choose another view or add materials to this track.</EmptyState>}
    {!!items.length && <ul className="track-list">{items.map((item) => <li key={item.artifact.id} className="track-card music-material">
      <div className="workspace-heading"><strong>{item.artifact.kind.replaceAll("_", " ")}</strong><Badge>{item.artifact.mime_type === "application/x-lrc" ? "Timestamped LRC" : item.artifact.mime_type === "text/plain" ? "Plain text" : item.artifact.mime_type}</Badge></div>
      <p className="material-provenance"><small>{item.derived ? "Derived" : "Original"}{item.source_provider ? ` via ${item.source_provider}` : ""} · {versions.find((v) => v.id === item.artifact.track_version_id)?.label ?? "Version"}</small></p>
      {item.attribution && <p><small>{item.attribution}</small></p>}
      {item.warnings?.map((warning, i) => <p key={i} role="note"><small>Note: {warning}</small></p>)}
      <DocumentViewer artifact={item.artifact} />
    </li>)}</ul>}
  </section>;
}
