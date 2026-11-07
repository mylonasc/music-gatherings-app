import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, post } from "../../lib/api-client";
import { useGet } from "../../lib/use-api";
import { ErrorNotice, Field, Loading } from "../../components/ui";

interface Profile {
  id: string;
  name: string;
  version: number;
  config: { steps?: unknown[]; outputs?: string[] };
  is_active: boolean;
}

const DEFAULT_STEPS = `[
  {"type": "normalize_sections", "config": {}},
  {"type": "transpose", "config": {"semitones": 2, "accidentals": "prefer_sharps"}}
]`;

export function ProcessingPanel() {
  const { data, error, loading, reload } = useGet<Profile[]>("/api/v1/admin/processing-profiles");
  const [name, setName] = useState("lyrics");
  const [stepsJson, setStepsJson] = useState(DEFAULT_STEPS);
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function createProfile(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setNotice(null);
    let steps: unknown;
    try {
      steps = JSON.parse(stepsJson) as unknown;
    } catch {
      setFormError("Steps must be valid JSON.");
      return;
    }
    if (!Array.isArray(steps)) {
      setFormError("Steps must be a JSON array.");
      return;
    }
    try {
      await post("/api/v1/admin/processing-profiles", {
        name: name.trim(),
        steps,
        outputs: ["canonical_json", "lyrics_html", "chord_chart_html"],
      });
      setNotice("Profile saved as a new version.");
      reload();
    } catch (err: unknown) {
      setFormError(err instanceof ApiError ? err.message : "Could not save the profile.");
    }
  }

  async function deactivate(id: string) {
    setNotice(null);
    try {
      await post(`/api/v1/admin/processing-profiles/${id}/deactivate`, {});
      setNotice("Profile deactivated.");
      reload();
    } catch (err: unknown) {
      setNotice(err instanceof ApiError ? err.message : "Deactivation failed.");
    }
  }

  if (loading) return <Loading label="Loading profiles…" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;

  return (
    <section aria-label="Processing profiles">
      <h3>Saved profiles</h3>
      {notice && <p role="status">{notice}</p>}
      {(data ?? []).length === 0 && <p role="status">No profiles yet.</p>}
      <ul>
        {(data ?? []).map((profile) => (
          <li key={profile.id}>
            {profile.name} v{profile.version} {profile.is_active ? "(active)" : "(inactive)"}{" "}
            {profile.is_active && (
              <button type="button" onClick={() => void deactivate(profile.id)}>
                Deactivate
              </button>
            )}
          </li>
        ))}
      </ul>
      <h3>New profile version</h3>
      <p>Steps are validated against the processor registry before saving.</p>
      <form onSubmit={(e) => void createProfile(e)} aria-label="New processing profile">
        {formError && <ErrorNotice message={formError} />}
        <Field id="profile-name" label="Profile name">
          <input
            id="profile-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </Field>
        <Field id="profile-steps" label="Steps (JSON array)">
          <textarea
            id="profile-steps"
            value={stepsJson}
            onChange={(e) => setStepsJson(e.target.value)}
            rows={6}
          />
        </Field>
        <button type="submit">Validate and save</button>
      </form>
      <ProcessorPreview />
    </section>
  );
}

export function ProcessorPreview() {
  const [source, setSource] = useState("[Verse]\nC G\nRow row row your boat\n");
  const [result, setResult] = useState<{ outputs?: Record<string, string>; warnings?: string[] } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function preview(event: FormEvent) {
    event.preventDefault();
    setRunning(true);
    setPreviewError(null);
    setResult(null);
    try {
      const response = await post<{ outputs?: Record<string, string>; warnings?: string[] }>(
        "/api/v1/admin/tests/process",
        {
          source_text: source,
          profile: {
            schema_version: 1,
            steps: [{ type: "transpose", config: { semitones: 2 } }],
            outputs: ["lyrics_html", "chord_chart_html"],
          },
        },
      );
      setResult(response);
    } catch (err: unknown) {
      setPreviewError(err instanceof ApiError ? err.message : "Preview failed.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <section aria-label="Processor preview">
      <h3>Preview (isolated — nothing is stored)</h3>
      <form onSubmit={(e) => void preview(e)} aria-label="Process a sample">
        {previewError && <ErrorNotice message={previewError} />}
        <Field id="preview-source" label="Sample chord chart">
          <textarea id="preview-source" value={source} onChange={(e) => setSource(e.target.value)} rows={5} />
        </Field>
        <button type="submit" disabled={running}>
          {running ? "Processing…" : "Preview"}
        </button>
      </form>
      {result && (
        <>
          {(result.warnings ?? []).length > 0 && (
            <ul aria-label="Preview warnings">
              {result.warnings!.map((warning, index) => (
                <li key={index} role="note">
                  {warning}
                </li>
              ))}
            </ul>
          )}
          {Object.entries(result.outputs ?? {}).map(([name, html]) => (
            <section key={name} aria-label={name}>
              <h4>{name}</h4>
              <div
                className="doc-panel"
                role="region"
                aria-label={`preview ${name}`}
                tabIndex={0}
                dangerouslySetInnerHTML={{ __html: html }}
              />
            </section>
          ))}
        </>
      )}
    </section>
  );
}
