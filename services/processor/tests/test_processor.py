"""Parser, transforms, renderers, and service contract tests with fixtures."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from processor.app import app as processor_app
from processor.models import CanonicalDocument
from processor.parse import parse_chart
from processor.render import render_chord_chart_html, render_lyrics_html, render_lyrics_text
from processor.transforms import apply_profile, validate_profile

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def expand_profile() -> dict:
    return {
        "schema_version": 1,
        "steps": [
            {"type": "normalize_sections", "config": {}},
            {
                "type": "expand_repeated_chords",
                "config": {"strategy": "matching_sections", "on_ambiguity": "warn"},
            },
            {"type": "transpose", "config": {"semitones": 2, "accidentals": "prefer_sharps"}},
        ],
        "outputs": ["canonical_json", "lyrics_text", "lyrics_html", "chord_chart_html"],
    }


def test_repeat_fixture_parses_and_expands() -> None:
    canonical, warnings = parse_chart(read_fixture("repeat.input.txt"))
    assert [s["label"] for s in canonical["sections"]] == ["Verse 1", "Chorus", "Chorus"]
    assert canonical["sections"][2]["repeat_of"] == canonical["sections"][1]["id"]
    # Second chorus has lyrics but no chords yet.
    assert canonical["sections"][2]["lines"][0]["chords"] == []

    transformed, transform_warnings = apply_profile(canonical, expand_profile())
    verse_chords = [c["chord"] for c in transformed["sections"][0]["lines"][0]["chords"]]
    assert verse_chords == ["D", "A"], verse_chords  # transposed +2, aligned to words
    repeated = transformed["sections"][2]["lines"][0]["chords"]
    assert [(c["chord"], c["position"]) for c in repeated] == [
        (c["chord"], c["position"])
        for c in transformed["sections"][1]["lines"][0]["chords"]
    ]
    assert not any("ambiguous" in w for w in warnings + transform_warnings)
    # Raw inputs preserved: lyrics untouched by expansion/transposition.
    assert transformed["sections"][0]["lines"][0]["lyrics"] == "Row row row your boat"


def test_ambiguous_repeat_warns_and_leaves_music_untouched() -> None:
    canonical, _ = parse_chart(
        "[Chorus]\nC G\nLine one here\nC F\nLine two here\n\n"
        "[Chorus]\nDifferent longer line here now\n"
    )
    transformed, warnings = apply_profile(
        canonical,
        {
            "schema_version": 1,
            "steps": [{"type": "expand_repeated_chords", "config": {}}],
            "outputs": ["canonical_json"],
        },
    )
    assert any("different line count" in w for w in warnings)
    assert transformed["sections"][1]["lines"][0]["chords"] == []


def test_brackets_tab_and_xss_escaping() -> None:
    canonical, _ = parse_chart(read_fixture("brackets_tab.input.txt"))
    section = canonical["sections"][0]
    assert section["lines"][0]["lyrics"] == "Hello world, this is a test"
    assert [c["chord"] for c in section["lines"][0]["chords"]] == ["C", "G/B"]
    assert len(section["tablature"]) == 6  # kept opaque

    lyrics_html = render_lyrics_html(canonical)
    assert "<script>" not in lyrics_html
    assert "&lt;script&gt;" in lyrics_html
    chart_html = render_chord_chart_html(canonical)
    assert "<script>" not in chart_html
    assert "G/B" in chart_html  # chords rendered, lyrics escaped
    text = render_lyrics_text(canonical)
    assert "Hello world" in text and "e|" in text


def test_profile_validation_rejects_garbage() -> None:
    assert validate_profile({"schema_version": 1, "steps": [], "outputs": []}) == []
    errors = validate_profile(
        {
            "schema_version": 1,
            "steps": [
                {"type": "transpose", "config": {"semitones": 99}},
                {"type": "nope", "config": {}},
                {"type": "transpose", "config": {"semitones": 1}},
            ],
            "outputs": [],
        }
    )
    assert any("semitones" in e for e in errors)
    assert any("unknown step: nope" in e for e in errors)
    assert any("duplicate step" in e for e in errors)
    order_errors = validate_profile(
        {
            "schema_version": 1,
            "steps": [
                {"type": "transpose", "config": {"semitones": 1}},
                {"type": "normalize_sections", "config": {}},
            ],
            "outputs": [],
        }
    )
    assert any("order" in e for e in order_errors)


def test_service_process_is_reproducible() -> None:
    client = TestClient(processor_app)
    assert client.get("/health").json()["status"] == "ok"
    assert "transpose" in client.get("/v1/capabilities").json()["steps"]
    valid = client.post(
        "/v1/validate-profile", json=expand_profile()
    ).json()
    assert valid == {"valid": True, "errors": []}
    invalid = client.post(
        "/v1/validate-profile",
        json={"schema_version": 1, "steps": [{"type": "nope", "config": {}}], "outputs": []},
    ).json()
    assert invalid["valid"] is False

    body = {
        "source_text": read_fixture("repeat.input.txt"),
        "profile": expand_profile(),
        "title": "Repeat Song",
    }
    first = client.post("/v1/process", json=body).json()
    second = client.post("/v1/process", json=body).json()
    assert first == second
    CanonicalDocument.model_validate(first["canonical"])
    assert set(first["outputs"]) == {
        "canonical_json",
        "lyrics_text",
        "lyrics_html",
        "chord_chart_html",
    }
    assert "D" in first["outputs"]["chord_chart_html"]
    assert first["processor_version"] == "0.1.0"

    bad = client.post(
        "/v1/process",
        json={
            "source_text": "hello",
            "profile": {
                "schema_version": 1,
                "steps": [{"type": "nope", "config": {}}],
                "outputs": [],
            },
        },
    ).json()
    assert bad["outputs"] == {}
    assert any("invalid profile" in w for w in bad["warnings"])


def test_canonical_json_output_round_trips() -> None:
    canonical, _ = parse_chart(read_fixture("repeat.input.txt"))
    transformed, _ = apply_profile(canonical, expand_profile())
    CanonicalDocument.model_validate(transformed)
    assert json.loads(json.dumps(transformed))["sections"][0]["lines"][0][
        "lyrics"
    ].startswith("Row")


def test_contracts_match_checked_in_schemas() -> None:
    from processor.models import CONTRACT_MODELS

    schema_dir = FIXTURES.parent.parent.parent.parent / "contracts" / "processor" / "v1"
    assert schema_dir.is_dir()
    checked_in = sorted(p.stem for p in schema_dir.glob("*.json"))
    assert checked_in == sorted(CONTRACT_MODELS), (
        "processor contract schemas out of sync; run python -m processor.gen_schemas"
    )
