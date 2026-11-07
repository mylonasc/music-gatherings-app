import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import type { ArtifactOut } from "../../../lib/api-types";
import { DocumentViewer, documentViewers } from "./DocumentViewer";
import { sanitizeMusicHtml } from "../../../lib/music-html";

it("removes active HTML and style while preserving music alignment markup", () => {
  const safe = sanitizeMusicHtml('<div class="chord-chart primary-nav" style="position:fixed"><pre class="chord-line">C   G</pre><span class="skip-link">hidden</span><script>alert(1)</script><img src=x onerror=alert(1)><a href="javascript:alert(1)">link</a><iframe srcdoc="x"></iframe></div>');
  expect(safe).toContain('<pre class="chord-line">C   G</pre>');
  expect(safe).not.toMatch(/script|onerror|iframe|href|style=|<img|primary-nav|skip-link/);
});
it("keeps unknown notation formats out of HTML dispatch", () => {
  const artifact = { id: "a1", kind: "sheet_music", mime_type: "application/pdf", is_external: false } as ArtifactOut;
  expect(documentViewers.find((v) => v.supports(artifact))).toBeUndefined();
  render(<DocumentViewer artifact={artifact} />);
  expect(screen.getByRole("link", { name: "Download material" })).toHaveAttribute("href", "/api/v1/artifacts/a1/content");
});
