import type { Reporter, TestCase, TestResult } from "@playwright/test/reporter";
import { copyFileSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const escape = (value: string) => value.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]!));

/** Standalone review gallery, including successful checkpoints and failed retries. */
export default class GalleryReporter implements Reporter {
  private entries: string[] = [];
  onBegin() { mkdirSync("review-gallery", { recursive: true }); }
  onTestEnd(test: TestCase, result: TestResult) {
    for (const attachment of result.attachments) {
      if (attachment.contentType !== "image/png" || !attachment.path) continue;
      const file = `${this.entries.length}-${test.parent.project()?.name ?? "setup"}.png`;
      copyFileSync(attachment.path, join("review-gallery", file));
      const label = escape(`${test.parent.project()?.name} · ${test.title} · ${attachment.name} · ${result.status} (retry ${result.retry})`);
      this.entries.push(`<figure><a href="${file}"><img loading="lazy" src="${file}" alt="${label}"></a><figcaption>${label}</figcaption></figure>`);
    }
  }
  onEnd() {
    writeFileSync("review-gallery/index.html", `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Music Gatherings UI review</title><style>body{font:16px system-ui;background:#f6f4ee;color:#20332f;margin:2rem}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:2rem}figure{margin:0;background:white;padding:1rem;border-radius:1rem}img{max-width:100%;max-height:700px;object-fit:contain}figcaption{overflow-wrap:anywhere}</style><h1>UI journey checkpoints</h1><p>Successful checkpoints and failure screenshots. Click an image for full resolution. Browser emulation is not real-device certification.</p><main>${this.entries.join("\n")}</main>`);
  }
}
