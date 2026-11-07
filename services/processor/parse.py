"""Plain-text chord-chart parser producing canonical documents.

Understands, conservatively and in order:
- ``[Section]`` headers (``[Chorus x2]`` marks a repeat of the earlier Chorus),
- chord-over-lyrics line pairs (chords anchored by column position),
- inline ``[C]`` brackets inside lyric lines,
- tab blocks (kept opaque, never transformed),
- bare lyric lines.

Anything unrecognized stays a lyric line. The parser never invents chords.
"""

import re

from .chords import is_chord_line, is_chord_token
from .models import ChordPlacement, LyricLine, Section, SectionKind

_HEADER_RE = re.compile(r"^\[(.+?)\](?:\s*[x×](\d+))?\s*$")
_BRACKET_RE = re.compile(r"\[([A-G][#b]?[^/\[\]\s]*?(?:/[A-G][#b]?)?)\]")
_TAB_LINE_RE = re.compile(r"^[eEBGDAF#|0-9xXhpb/\\~()\s\-+*.]+$")
_MAX_TAB_LINES_PER_SECTION = 200
_MAX_LINES_PER_SECTION = 2000

_KIND_KEYWORDS: tuple[tuple[SectionKind, tuple[str, ...]], ...] = (
    ("pre_chorus", ("pre-chorus", "prechorus", "pre chorus")),
    ("verse", ("verse", "vers", "strophe")),
    ("chorus", ("chorus", "refrain", "hook")),
    ("bridge", ("bridge",)),
    ("intro", ("intro", "introduction")),
    ("outro", ("outro", "coda", "ending")),
    ("solo", ("solo", "instrumental")),
    ("interlude", ("interlude", "break")),
)


def _classify_kind(label: str) -> SectionKind:
    lowered = label.lower()
    for kind, keywords in _KIND_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return kind
    return "custom"


def _is_tab_line(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 4:
        return False
    if not _TAB_LINE_RE.fullmatch(line.rstrip("\n")):
        return False
    has_digits = any(ch.isdigit() for ch in stripped)
    staff_like = "|" in stripped and (has_digits or stripped.count("-") >= 4)
    return staff_like or (has_digits and stripped.count("-") >= 4)


def _chords_from_brackets(text: str) -> tuple[str, list[ChordPlacement]]:
    placements: list[ChordPlacement] = []
    output: list[str] = []
    position = 0
    cursor = 0
    for match in _BRACKET_RE.finditer(text):
        chord = match.group(1)
        if not is_chord_token(chord):
            continue
        output.append(text[cursor : match.start()])
        position += match.start() - cursor
        placements.append(ChordPlacement(position=position, chord=chord))
        cursor = match.end()
    output.append(text[cursor:])
    return "".join(output), placements


def _chords_from_alignment(chord_line: str, lyric_line: str) -> list[ChordPlacement]:
    placements: list[ChordPlacement] = []
    for match in re.finditer(r"\S+", chord_line):
        token = match.group(0)
        if not is_chord_token(token):
            continue
        column = match.start()
        position = min(column, len(lyric_line))
        # Snap to the next non-space so chords sit on sung syllables.
        while position < len(lyric_line) and lyric_line[position] == " ":
            position += 1
        placements.append(ChordPlacement(position=min(position, len(lyric_line)), chord=token))
    placements.sort(key=lambda placement: placement.position)
    return placements


def parse_chart(
    text: str, *, title: str | None = None, artist: str | None = None
) -> tuple[dict, list[str]]:
    """Parse text into a canonical-document dict plus parser warnings."""
    from .models import CanonicalDocument

    warnings: list[str] = []
    sections: list[Section] = []
    current = Section(id="section-1", kind="custom", label="Section 1")
    sections.append(current)
    seen_labels: dict[str, str] = {}
    pending_chords: str | None = None
    counter = 1

    def new_section(label: str, repeat_count: int = 1) -> Section:
        nonlocal counter
        counter += 1
        section = Section(
            id=f"section-{counter}",
            kind=_classify_kind(label),
            label=label,
            repeat_count=repeat_count,
        )
        key = label.strip().lower()
        if key in seen_labels and repeat_count == 1:
            section.repeat_of = seen_labels[key]
        else:
            seen_labels.setdefault(key, section.id)
        sections.append(section)
        return section

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        raw = lines[index].rstrip("\n")
        line = raw.rstrip()
        index += 1
        if not line.strip():
            pending_chords = None
            continue
        header = _HEADER_RE.fullmatch(line.strip())
        if header:
            label, times = header.group(1).strip(), header.group(2)
            current = new_section(label or f"Section {counter + 1}", int(times or 1))
            pending_chords = None
            continue
        if _is_tab_line(line):
            block = [line]
            while (
                index < len(lines)
                and _is_tab_line(lines[index])
                and len(block) < _MAX_TAB_LINES_PER_SECTION
            ):
                block.append(lines[index].rstrip())
                index += 1
            current.tablature.extend(block)
            pending_chords = None
            continue
        if is_chord_line(line.strip()) and pending_chords is None:
            pending_chords = line
            continue
        lyrics, inline = _chords_from_brackets(line.strip())
        aligned: list[ChordPlacement] = []
        if pending_chords is not None:
            aligned = _chords_from_alignment(pending_chords, lyrics)
            if not aligned and not inline:
                warnings.append(
                    f"chord line above {lyrics[:40]!r} matched no lyrics; kept as lyric line"
                )
                if len(current.lines) < _MAX_LINES_PER_SECTION:
                    current.lines.append(LyricLine(lyrics=pending_chords.strip(), chords=[]))
            pending_chords = None
        merged = sorted(inline + aligned, key=lambda placement: placement.position)
        if len(current.lines) >= _MAX_LINES_PER_SECTION:
            warnings.append(f"section {current.label!r} truncated: too many lines")
            break
        current.lines.append(LyricLine(lyrics=lyrics, chords=merged))

    if pending_chords is not None:
        current.lines.append(LyricLine(lyrics=pending_chords.strip(), chords=[]))

    document = CanonicalDocument(
        title=title,
        artist=artist,
        sections=[s for s in sections if s.lines or s.tablature or s.repeat_of],
    )
    return document.model_dump(), warnings
