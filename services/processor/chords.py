"""Chord recognition and transposition.

Roots are case-sensitive uppercase A-G (lyric words like "am" never match).
Suffixes are preserved verbatim; only roots (and slash bass notes) move.
Unrecognized spellings are left unchanged with a warning, never guessed.
"""

import re

_CHORD_RE = re.compile(r"^([A-G])([#b]?)([^/\s]*)(?:/([A-G])([#b]?))?$")
_SUFFIX_RE = re.compile(r"^[mM0-9+#b°ø()susadddimaj]*$")

SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_INDEX = {name: i for i, name in enumerate(SHARPS)}
_INDEX.update({"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10})
_ENHARMONIC = {"B#": "C", "E#": "F", "Cb": "B", "Fb": "E"}


def is_chord_token(token: str) -> bool:
    match = _CHORD_RE.fullmatch(token)
    if not match:
        return False
    _root, _acc, suffix, _bass, _bass_acc = match.groups()
    return bool(_SUFFIX_RE.fullmatch(suffix or ""))


def is_chord_line(line: str) -> bool:
    tokens = line.split()
    return bool(tokens) and all(is_chord_token(token) for token in tokens)


def _transpose_note(note: str, semitones: int, prefer_flats: bool) -> str | None:
    canonical = _ENHARMONIC.get(note, note)
    if canonical not in _INDEX:
        return None
    index = (_INDEX[canonical] + semitones) % 12
    return FLATS[index] if prefer_flats else SHARPS[index]


def transpose_chord(chord: str, semitones: int, prefer_flats: bool = False) -> str | None:
    """Transpose a chord symbol; returns None when it cannot be done safely."""
    if not is_chord_token(chord):
        return None
    match = _CHORD_RE.fullmatch(chord)
    assert match is not None
    root, acc, suffix, bass, bass_acc = match.groups()
    new_root = _transpose_note(root + (acc or ""), semitones, prefer_flats)
    if new_root is None:
        return None
    if bass:
        new_bass = _transpose_note(bass + (bass_acc or ""), semitones, prefer_flats)
        if new_bass is None:
            return None
        return f"{new_root}{suffix}/{new_bass}"
    return f"{new_root}{suffix}"
