import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { ErrorNotice, Field } from "../../components/ui";
import { post } from "../../lib/api-client";
import type { VersionDetailOut, VersionOut } from "../../lib/api-types";

const kinds = ["lyrics", "chord_chart", "tablature", "sheet_music"] as const;

export function MaterialForm({ trackId, versions, onSaved }: { trackId: string; versions: VersionDetailOut[]; onSaved: () => void }) {
  const [mode, setMode] = useState("upload");
  const [version, setVersion] = useState(versions[0]?.id ?? "");
  const [kind, setKind] = useState<string>("lyrics");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const lock = useRef(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (lock.current) return;
    setError(null); setSaved(false);
    if (mode === "upload" && !file) { setError("Choose a file."); return; }
    if (mode === "reference" && !/^https?:\/\//i.test(url.trim())) { setError("Enter an http or https link."); return; }
    lock.current = true; setBusy(true);
    try {
      let versionId = version;
      if (!versionId) {
        const created = await post<VersionOut>(`/api/v1/tracks/${trackId}/versions`, { label: "Personal materials" });
        versionId = created.id; setVersion(versionId);
      }
      const base = `/api/v1/tracks/${trackId}/versions/${versionId}/artifacts`;
      if (mode === "upload" && file) {
        const body = new FormData(); body.set("file", file); body.set("kind", kind);
        await post(`${base}/upload`, body);
      } else await post(`${base}/reference`, { kind, external_url: url.trim() });
      setSaved(true); onSaved();
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save material."); }
    finally { lock.current = false; setBusy(false); }
  }
  return <details className="surface-panel"><summary>Add materials to this track</summary>
    <p>Original files stay unchanged. PDFs, images and tablature may be download-only; no notation conversion is implied.</p>
    <form aria-label="Add material" onSubmit={submit}>
      {error && <ErrorNotice message={error} />}{saved && <p role="status">Material saved.</p>}
      <fieldset disabled={busy}><legend>Material details</legend>
        <Field id="material-version" label="Musical version"><select id="material-version" value={version} onChange={(e) => setVersion(e.target.value)}>
          <option value="">New personal materials version</option>{versions.map((v) => <option key={v.id} value={v.id}>{v.label ?? "Version"}</option>)}
        </select></Field>
        <Field id="material-kind" label="Material type"><select id="material-kind" value={kind} onChange={(e) => setKind(e.target.value)}>{kinds.map((k) => <option key={k} value={k}>{k.replaceAll("_", " ")}</option>)}</select></Field>
        <Field id="material-method" label="Attach by"><select id="material-method" value={mode} onChange={(e) => setMode(e.target.value)}><option value="upload">Upload a file</option><option value="reference">External link</option></select></Field>
        {mode === "upload" ? <Field id="material-file" label="File"><input id="material-file" type="file" accept=".txt,.md,.pdf,.png,.jpg,.jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
          : <Field id="material-url" label="Source URL"><input id="material-url" type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" /></Field>}
      </fieldset>
      <button disabled={busy} type="submit">{busy ? "Saving…" : "Save material"}</button>
      <p><small>If a connection drops after saving, check the materials list before retrying.</small></p>
    </form>
  </details>;
}
