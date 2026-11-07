import DOMPurify from "dompurify";

/** Restrict music markup to inert structural elements; never trust provenance alone. */
export function sanitizeMusicHtml(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["div", "p", "pre", "span", "br", "strong", "em", "h2", "h3", "h4"],
    ALLOWED_ATTR: ["class"], ALLOW_DATA_ATTR: false, ALLOW_ARIA_ATTR: false,
  });
}
