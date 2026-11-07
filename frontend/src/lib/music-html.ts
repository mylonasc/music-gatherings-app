import DOMPurify from "dompurify";

/** Restrict music markup to inert structural elements; never trust provenance alone. */
export function sanitizeMusicHtml(html: string): string {
  const fragment = DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ["div", "p", "pre", "span", "br", "strong", "em", "h2", "h3", "h4"],
    ALLOWED_ATTR: ["class"], ALLOW_DATA_ATTR: false, ALLOW_ARIA_ATTR: false,
    RETURN_DOM_FRAGMENT: true,
  });
  // Application classes can position content over navigation/forms. Only music
  // renderer classes may survive, even though the markup itself is inert.
  const musicClasses = new Set(["song", "chord-chart", "chord-line", "chord"]);
  for (const element of fragment.querySelectorAll("[class]")) {
    const allowed = Array.from(element.classList).filter((name) => musicClasses.has(name));
    if (allowed.length) element.setAttribute("class", allowed.join(" "));
    else element.removeAttribute("class");
  }
  const container = document.createElement("div");
  container.append(fragment);
  return container.innerHTML;
}
