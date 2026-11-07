/**
 * Sanitize FTS5 snippets for innerHTML rendering.
 *
 * The backend marks matches with literal <b>…</b> tags, but the surrounding
 * text is user-supplied (titles, lyrics) and must never execute. Escape
 * everything, then restore only the backend's own markers.
 */
export function sanitizeSnippet(snippet: string): string {
  const escaped = snippet
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
  return escaped.replaceAll("&lt;b&gt;", "<b>").replaceAll("&lt;/b&gt;", "</b>");
}
