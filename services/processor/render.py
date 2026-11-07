"""Renderers: escaped HTML/text outputs from canonical documents.

All lyric, chord, and label text is HTML-escaped at render time. There is no
raw-HTML passthrough: active markup in source material renders as inert text.
"""

import html


def render_lyrics_text(document: dict) -> str:
    parts: list[str] = []
    for section in document.get("sections", []):
        parts.append(f"[{section.get('label', '')}]")
        for line in section.get("lines", []):
            parts.append(line.get("lyrics", ""))
        for tab_line in section.get("tablature", []):
            parts.append(tab_line)
        parts.append("")
    return "\n".join(parts).strip() + "\n"


def render_lyrics_html(document: dict, title: str | None = None) -> str:
    heading = f"<h1>{html.escape(title)}</h1>\n" if title else ""
    chunks = [heading + '<div class="song">']
    for section in document.get("sections", []):
        chunks.append(
            f'<section aria-label="{html.escape(str(section.get("label", "")))}">'
        )
        chunks.append(f"<h2>{html.escape(str(section.get('label', '')))}</h2>")
        for line in section.get("lines", []):
            chunks.append(f"<p>{html.escape(line.get('lyrics', ''))}</p>")
        if section.get("tablature"):
            tab = "\n".join(html.escape(line) for line in section["tablature"])
            chunks.append("<pre>" + tab + "</pre>")
        chunks.append("</section>")
    chunks.append("</div>")
    return "\n".join(chunks) + "\n"


def render_chord_chart_html(document: dict, title: str | None = None) -> str:
    heading = f"<h1>{html.escape(title)}</h1>\n" if title else ""
    chunks = [heading + '<div class="song chord-chart">']
    for section in document.get("sections", []):
        chunks.append(
            f'<section aria-label="{html.escape(str(section.get("label", "")))}">'
        )
        chunks.append(f"<h2>{html.escape(str(section.get('label', '')))}</h2>")
        for line in section.get("lines", []):
            lyrics = line.get("lyrics", "")
            chords = sorted(line.get("chords", []), key=lambda c: c["position"])
            if chords:
                annotations = "".join(
                    f'<span class="chord" data-pos="{c["position"]}">'
                    f"{html.escape(c['chord'])}</span> "
                    for c in chords
                )
                chunks.append(f'<div class="chord-line">{annotations.strip()}</div>')
            chunks.append(f"<p>{html.escape(lyrics)}</p>")
        if section.get("tablature"):
            tab = "\n".join(html.escape(line) for line in section["tablature"])
            chunks.append("<pre>" + tab + "</pre>")
        chunks.append("</section>")
    chunks.append("</div>")
    return "\n".join(chunks) + "\n"
