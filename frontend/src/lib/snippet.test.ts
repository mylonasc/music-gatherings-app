import { describe, expect, it } from "vitest";
import { sanitizeSnippet } from "./snippet";

describe("sanitizeSnippet", () => {
  it("restores backend match markers", () => {
    expect(sanitizeSnippet("Blue <b>Train</b>")).toBe("Blue <b>Train</b>");
  });

  it("neutralizes active markup from user content", () => {
    const out = sanitizeSnippet('<script>alert(1)</script> <b>hit</b> <img src=x onerror=y>');
    expect(out).not.toContain("<script>");
    expect(out).not.toContain("<img");
    expect(out).toContain("<b>hit</b>");
    expect(out).toContain("&lt;script&gt;");
  });

  it("escapes stray angle brackets", () => {
    expect(sanitizeSnippet("a < b and c > d")).toBe("a &lt; b and c &gt; d");
  });
});
