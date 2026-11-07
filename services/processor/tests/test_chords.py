"""Chord recognition and transposition."""

import pytest

from processor.chords import is_chord_line, is_chord_token, transpose_chord


@pytest.mark.parametrize(
    "token",
    ["C", "G", "Am", "F#m7", "Bb", "Dsus4", "G/B", "Cmaj7", "Em9", "A#dim", "NoChord", "H"],
)
def test_chord_token_recognition(token: str) -> None:
    assert is_chord_token(token) == (token not in ("NoChord", "H"))


@pytest.mark.parametrize("token", ["am", "hello", "", "C# #", "A/bb"])
def test_lyric_words_are_not_chords(token: str) -> None:
    assert not is_chord_token(token)
    assert not is_chord_line(token)


def test_chord_line_with_spaces_between_chords() -> None:
    assert is_chord_line("C D")  # two chord tokens make a chord line


def test_chord_lines_need_every_token() -> None:
    assert is_chord_line("C G Am F")
    assert not is_chord_line("C row your G")
    assert not is_chord_line("")


@pytest.mark.parametrize(
    "chord,semitones,expected",
    [
        ("C", 2, "D"),
        ("B", 1, "C"),
        ("F", -1, "E"),
        ("G/B", 2, "A/C#"),
        ("Bb", 2, "C"),
        ("F#", -1, "F"),
        ("Am7", 0, "Am7"),
        ("Dsus4", 7, "Asus4"),
        ("Ebmaj7", -3, "Cmaj7"),
    ],
)
def test_transpose(chord: str, semitones: int, expected: str) -> None:
    assert transpose_chord(chord, semitones) == expected


def test_transpose_prefers_flats_on_request() -> None:
    assert transpose_chord("C", 1, prefer_flats=True) == "Db"
    assert transpose_chord("C", 1, prefer_flats=False) == "C#"


def test_untransposable_chords_return_none() -> None:
    assert transpose_chord("notachord", 2) is None
    assert transpose_chord("H", 2) is None
