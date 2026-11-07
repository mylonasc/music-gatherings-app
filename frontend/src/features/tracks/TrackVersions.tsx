import type { VersionDetailOut } from "../../lib/api-types";

/** Inventory is separate from inline reading and material attachment workflows. */
export function TrackVersions({ versions }: { versions: VersionDetailOut[] }) {
  return <div className="version-inventory">{versions.map((version) => <section className="surface-panel" key={version.id} aria-label={version.label ?? "Version"}>
    <h4>{version.label ?? "Version"}</h4>
    <p className="version-facts">{[version.musical_key && `Key: ${version.musical_key}`, version.tuning && `Tuning: ${version.tuning}`, version.capo != null && `Capo: ${version.capo}`, version.language && `Language: ${version.language}`].filter(Boolean).join(" · ")}</p>
    {version.notes && <p>{version.notes}</p>}
    {!version.artifacts?.length && <p>No materials attached yet.</p>}
    <ul className="material-inventory">{version.artifacts?.map((artifact) => <li key={artifact.id}>
      <span>{artifact.kind.replaceAll("_", " ")} <small>({artifact.mime_type})</small></span>{" "}
      {artifact.is_external && artifact.external_url ? <a href={artifact.external_url} target="_blank" rel="noreferrer">open external reference</a> : <a href={`/api/v1/artifacts/${artifact.id}/content`}>download{artifact.file_name ? ` ${artifact.file_name}` : ""}</a>}
    </li>)}</ul>
  </section>)}</div>;
}
