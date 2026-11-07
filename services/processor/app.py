"""Normalization/post-processing private microservice (v1)."""

from fastapi import FastAPI

from .models import (
    CanonicalDocument,
    DiagnosticResponse,
    ProcessingProfile,
    ProcessRequest,
    ProcessResponse,
)
from .parse import parse_chart
from .render import render_chord_chart_html, render_lyrics_html, render_lyrics_text
from .transforms import apply_profile, registered_steps, validate_profile

SERVICE_NAME = "processor"
SERVICE_VERSION = "0.1.0"

MAX_SECTIONS = 500
MAX_OUTPUT_BYTES = 2_000_000


def create_app() -> FastAPI:
    app = FastAPI(title="Music Gatherings Processor", version=SERVICE_VERSION)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": SERVICE_NAME, "version": SERVICE_VERSION}

    @app.get("/v1/capabilities")
    def capabilities() -> dict:
        return {
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "steps": registered_steps(),
            "outputs": ["canonical_json", "lyrics_text", "lyrics_html", "chord_chart_html"],
            "limits": {"max_sections": MAX_SECTIONS, "max_output_bytes": MAX_OUTPUT_BYTES},
        }

    @app.post("/v1/validate-profile", response_model=DiagnosticResponse)
    def validate(body: ProcessingProfile) -> DiagnosticResponse:
        errors = validate_profile(body.model_dump())
        return DiagnosticResponse(valid=not errors, errors=errors)

    @app.post("/v1/process", response_model=ProcessResponse)
    def process(body: ProcessRequest) -> ProcessResponse:
        errors = validate_profile(body.profile.model_dump())
        if errors:
            return ProcessResponse(
                canonical=CanonicalDocument(),
                outputs={},
                warnings=[f"invalid profile: {e}" for e in errors],
            )
        canonical, parse_warnings = parse_chart(
            body.source_text, title=body.title, artist=body.artist
        )
        if len(canonical.get("sections", [])) > MAX_SECTIONS:
            canonical["sections"] = canonical["sections"][:MAX_SECTIONS]
            parse_warnings.append("too many sections; truncated")
        transformed, transform_warnings = apply_profile(canonical, body.profile.model_dump())
        outputs: dict[str, str] = {}
        for name in body.profile.outputs:
            if name == "canonical_json":
                import json

                rendered = json.dumps(transformed, indent=2, sort_keys=True)
            elif name == "lyrics_text":
                rendered = render_lyrics_text(transformed)
            elif name == "lyrics_html":
                rendered = render_lyrics_html(transformed, title=body.title)
            elif name == "chord_chart_html":
                rendered = render_chord_chart_html(transformed, title=body.title)
            else:
                continue
            if len(rendered.encode("utf-8")) > MAX_OUTPUT_BYTES:
                transform_warnings.append(f"output {name} exceeded size limit; omitted")
                continue
            outputs[name] = rendered
        return ProcessResponse(
            canonical=CanonicalDocument.model_validate(transformed),
            outputs=outputs,
            warnings=parse_warnings + transform_warnings,
        )

    return app


app = create_app()
