import { sanitizeMusicHtml } from "../../../lib/music-html";
import type { ComponentType } from "react";
import { ErrorNotice, Loading } from "../../../components/ui";
import type { ArtifactOut } from "../../../lib/api-types";
import { useText } from "../../../lib/use-api";

type ViewerProps = { artifact: ArtifactOut };
type ViewerDefinition = { id: string; supports: (artifact: ArtifactOut) => boolean; component: ComponentType<ViewerProps> };

function TextViewer({ artifact }: ViewerProps) {
  const { data, error, loading, reload } = useText(`/api/v1/artifacts/${artifact.id}/content`);
  if (loading) return <Loading label="Loading document…" />;
  if (error || data === null) return <ErrorNotice message={error ?? "Document unavailable."} onRetry={reload} />;
  return <pre className="doc-panel" role="region" aria-label={`${artifact.kind.replaceAll("_", " ")} document`} tabIndex={0}>{data}</pre>;
}

function HtmlViewer({ artifact }: ViewerProps) {
  const { data, error, loading, reload } = useText(`/api/v1/artifacts/${artifact.id}/content`);
  if (loading) return <Loading label="Loading document…" />;
  if (error || data === null) return <ErrorNotice message={error ?? "Document unavailable."} onRetry={reload} />;
  return <div className="doc-panel" role="region" aria-label={`${artifact.kind.replaceAll("_", " ")} document`} tabIndex={0}
    dangerouslySetInnerHTML={{ __html: sanitizeMusicHtml(data) }} />;
}

// Ordered definitions are the only dispatch seam. Future PDF/tab viewers add
// their own module and entry; unknown kinds must not fall into an HTML renderer.
export const documentViewers: readonly ViewerDefinition[] = [
  { id: "text", supports: (a) => ["text/plain", "application/x-lrc"].includes(a.mime_type), component: TextViewer },
  { id: "safe-music-html", supports: (a) => a.mime_type === "text/html" && ["rendered_lyrics", "rendered_chord_chart"].includes(a.kind), component: HtmlViewer },
];

export function DocumentViewer({ artifact }: ViewerProps) {
  if (artifact.is_external) return artifact.external_url ? <a href={artifact.external_url} target="_blank" rel="noreferrer">open external reference</a> : <ErrorNotice message="Reference unavailable." />;
  const Viewer = documentViewers.find((viewer) => viewer.supports(artifact))?.component;
  return Viewer ? <Viewer key={artifact.id} artifact={artifact} /> : <p className="feedback">Preview not available for this format. <a href={`/api/v1/artifacts/${artifact.id}/content`}>Download material</a></p>;
}
