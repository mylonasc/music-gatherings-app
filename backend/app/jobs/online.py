"""Online provider orchestration: search jobs and explicit imports.

Search never mutates the library. Imports attach fetched content to a new or
existing track/version with full provenance, deduplicate retries, and
optionally derive rendered representations via the processor microservice.

Rate-limit story (see S07/S10): per-user quotas are enforced at the API
endpoints; provider capacity is bounded by inbound gates inside each
provider service plus bounded job retries with cooldowns.
"""

from typing import Any

import httpx

from app.core.config import Settings
from app.jobs.context import FatalJobError, JobContext, RetryLater

# Tests override transports to drive the fake provider / processor in-process.
# Production uses plain HTTP on the private Compose network.
PROVIDER_TRANSPORTS: dict[str, httpx.BaseTransport | None] = {}
PROCESSOR_TRANSPORT: httpx.BaseTransport | None = None

PROCESSOR_VERSION = "0.1.0"
MAX_RETRY_AFTER_SECONDS = 300.0


class ProviderFailure(Exception):
    pass


def provider_client(provider: str, settings: Settings) -> httpx.Client:
    try:
        base_url = settings.online_provider_urls[provider]
    except KeyError:
        raise ProviderFailure(f"unknown provider: {provider}") from None
    transport = PROVIDER_TRANSPORTS.get(provider)
    return httpx.Client(
        base_url=base_url,
        transport=transport,
        timeout=settings.provider_timeout_seconds,
        follow_redirects=False,
    )


def parse_retry_after_seconds(value: str | None) -> float:
    if not value:
        return 30.0
    try:
        return max(0.0, min(MAX_RETRY_AFTER_SECONDS, float(value.strip())))
    except ValueError:
        return 30.0


def post_provider(
    client: httpx.Client, operation: str, path: str, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        response = client.post(path, json=payload)
    except httpx.TimeoutException as exc:
        raise ProviderFailure(f"{operation} timed out: {exc}") from exc
    except httpx.ConnectError as exc:
        raise ProviderFailure(f"{operation} unreachable: {exc}") from exc
    except httpx.HTTPError as exc:
        raise ProviderFailure(f"{operation} http error: {exc}") from exc
    if response.status_code == 429:
        raise RetryLater(
            parse_retry_after_seconds(response.headers.get("retry-after")),
            f"provider throttled {operation}",
        )
    if response.status_code >= 400:
        code, detail = _error_code_and_detail(response)
        message = f"{operation} failed ({response.status_code}) [{code or 'error'}]: {detail}"
        if code in ("provider_unavailable", "not_configured", "forbidden", "not_found"):
            # Definitive answers: retrying cannot help, fail fast.
            raise FatalJobError(message)
        if 400 <= response.status_code < 500:
            raise FatalJobError(message)
        raise ProviderFailure(message)
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderFailure(f"{operation} returned invalid JSON") from exc
    if not isinstance(body, dict):
        raise ProviderFailure(f"{operation} returned unexpected payload")
    return body


def _error_code_and_detail(response: httpx.Response) -> tuple[str, str]:
    try:
        body = response.json()
    except ValueError:
        return "", (response.text or "")[:200]
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        error = body["error"]
        return str(error.get("code", "")), str(error.get("message", ""))[:200]
    return "", (response.text or "")[:200]


def _error_detail(response: httpx.Response) -> str:
    return _error_code_and_detail(response)[1]


def handle_online_search(ctx: JobContext) -> dict[str, Any]:
    payload = ctx.payload
    query = str(payload.get("query", "")).strip()
    providers = list(payload.get("providers") or [])
    artifact_types = list(payload.get("artifact_types") or [])
    if not query:
        raise ProviderFailure("empty query")
    if not providers:
        raise ProviderFailure("no providers requested")
    settings = ctx.settings
    results: dict[str, Any] = {}
    for position, provider in enumerate(providers):
        ctx.check_cancelled()
        ctx.set_progress(position / len(providers))
        with provider_client(provider, settings) as client:
            body = post_provider(
                client,
                f"{provider}/search",
                "/v1/search",
                {"query": query, "artifact_types": artifact_types, "limit": 10},
            )
        results[provider] = body.get("items", [])
    ctx.set_progress(1.0)
    return {"query": query, "results": results}


def handle_online_import(ctx: JobContext) -> dict[str, Any]:
    """Fetch provider content and attach it to a track/version idempotently."""
    from app.models import Artifact, SourceRecord
    from app.search.index import reindex_track

    payload = ctx.payload
    provider = str(payload.get("provider", ""))
    external_id = str(payload.get("external_id", ""))
    crew_id = payload.get("crew_id")
    if not provider or not external_id or not crew_id:
        raise ProviderFailure("import requires provider, external_id, and crew_id")
    ctx.check_cancelled()
    ctx.set_progress(0.05, "fetching from provider")

    settings = ctx.settings
    with provider_client(provider, settings) as client:
        fetched = post_provider(
            client,
            f"{provider}/fetch",
            "/v1/fetch",
            {
                "external_id": external_id,
                "artifact_types": list(payload.get("artifact_types") or []),
            },
        )

    db = ctx.db

    title = fetched.get("title")
    artist = fetched.get("artist")
    track = _resolve_track(db, ctx, crew_id, title, artist)
    version = _resolve_version(db, ctx, track, payload.get("version_id"))
    ctx.check_cancelled()

    deduped = _find_existing_import(db, provider, external_id, version.id)
    if deduped is not None:
        return {
            "track_id": track.id,
            "version_id": version.id,
            "artifact_ids": deduped,
            "reused": True,
            "warnings": [],
        }

    source_url = fetched.get("source_url")
    source = SourceRecord(
        track_version_id=version.id,
        provider=provider,
        external_id=external_id,
        source_url=source_url,
        attribution=f"via {provider}",
        storage_permission="unknown",
        created_by_id=payload.get("created_by_id"),
    )
    db.add(source)
    db.flush()

    warnings: list[str] = []
    created_ids: list[str] = []
    stored_texts: list[tuple[str, str]] = []  # (artifact_id, text)
    requested = list(payload.get("artifact_types") or [])

    for item in fetched.get("artifacts", []):
        kind = str(item.get("artifact_type", ""))
        if requested and kind not in requested:
            continue
        content = _decode_content(item)
        allowed = bool(item.get("storage_allowed", False))
        if content is None or not allowed:
            artifact = Artifact(
                track_version_id=version.id,
                source_record_id=source.id,
                kind=kind or "lyrics",
                mime_type="text/uri-list",
                is_external=True,
                external_url=source_url,
                created_by_id=payload.get("created_by_id"),
            )
            if not allowed:
                warnings.append(f"{kind or 'content'} is reference-only; not stored")
            db.add(artifact)
            db.flush()
            created_ids.append(artifact.id)
            continue
        if len(content) > settings.max_object_bytes:
            warnings.append(f"{kind} exceeds size limit; kept as reference")
            artifact = Artifact(
                track_version_id=version.id,
                source_record_id=source.id,
                kind=kind or "lyrics",
                mime_type="text/uri-list",
                is_external=True,
                external_url=source_url,
                created_by_id=payload.get("created_by_id"),
            )
            db.add(artifact)
            db.flush()
            created_ids.append(artifact.id)
            continue
        stored = ctx.store.put(content)
        source.storage_permission = "allowed"
        artifact = Artifact(
            track_version_id=version.id,
            source_record_id=source.id,
            kind=kind or "lyrics",
            mime_type=str(item.get("mime_type") or "text/plain"),
            byte_size=stored.size,
            sha256=stored.sha256,
            object_key=stored.key,
            created_by_id=payload.get("created_by_id"),
        )
        db.add(artifact)
        db.flush()
        created_ids.append(artifact.id)
        if artifact.mime_type == "text/plain":
            try:
                stored_texts.append((artifact.id, content.decode("utf-8")))
            except UnicodeDecodeError:
                warnings.append(f"{kind} is not UTF-8 text; skipped for processing")

    if not created_ids and source_url:
        # Providers like Genius return metadata only: keep an explicit reference.
        kind = requested[0] if requested else "lyrics"
        artifact = Artifact(
            track_version_id=version.id,
            source_record_id=source.id,
            kind=kind,
            mime_type="text/uri-list",
            is_external=True,
            external_url=source_url,
            created_by_id=payload.get("created_by_id"),
        )
        db.add(artifact)
        db.flush()
        created_ids.append(artifact.id)
        warnings.append("provider returned metadata only; stored as reference")

    ctx.set_progress(0.7, "processing representations")
    profile = payload.get("profile")
    if profile and stored_texts:
        derived_ids, derivation_warnings = _derive_representations(
            ctx, version.id, stored_texts, profile, payload.get("created_by_id")
        )
        created_ids.extend(derived_ids)
        warnings.extend(derivation_warnings)

    reindex_track(db, ctx.store, track.id)
    ctx.set_progress(1.0)
    return {
        "track_id": track.id,
        "version_id": version.id,
        "artifact_ids": created_ids,
        "reused": False,
        "warnings": warnings,
    }


def _resolve_track(db, ctx: JobContext, crew_id: str, title: Any, artist: Any):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import CrewTrack, SourceRecord, Track, TrackVersion

    track_id = ctx.payload.get("track_id")
    if track_id:
        track = db.get(Track, track_id)
        if track is None:
            raise ProviderFailure("target track not found")
        listed = (
            db.execute(
                select(CrewTrack).where(
                    CrewTrack.crew_id == crew_id, CrewTrack.track_id == track.id
                )
            ).first()
            is not None
        )
        if not listed:
            raise ProviderFailure("target track is not in this crew")
        return track
    # Same provider item imported twice is the same content: reuse the track
    # that already references it instead of duplicating, so job retries and
    # repeated imports converge instead of multiplying tracks.
    existing = (
        db.execute(
            select(Track)
            .join(TrackVersion, TrackVersion.track_id == Track.id)
            .join(
                SourceRecord,
                SourceRecord.track_version_id == TrackVersion.id,
            )
            .where(
                SourceRecord.provider == ctx.payload.get("provider"),
                SourceRecord.external_id == ctx.payload.get("external_id"),
            )
        )
        .scalars()
        .all()
    )
    for candidate in existing:
        listed = (
            db.execute(
                select(CrewTrack).where(
                    CrewTrack.crew_id == crew_id, CrewTrack.track_id == candidate.id
                )
            ).first()
            is not None
        )
        if listed:
            return candidate
    track = Track(
        title=str(title)[:256] if title else None,
        artist=str(artist)[:256] if artist else None,
        created_by_id=ctx.payload.get("created_by_id"),
    )
    db.add(track)
    db.flush()
    db.add(
        CrewTrack(
            crew_id=crew_id,
            track_id=track.id,
            added_by_id=ctx.payload.get("created_by_id"),
            notes=f"imported via {ctx.payload.get('provider')}",
        )
    )
    db.flush()
    return track


def _resolve_version(db, ctx: JobContext, track, version_id: Any):  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import TrackVersion

    if version_id:
        version = db.get(TrackVersion, version_id)
        if version is None or version.track_id != track.id:
            raise ProviderFailure("target version not found")
        return version
    label = str(ctx.payload.get("version_label") or "Imported")[:128]
    existing = (
        db.execute(
            select(TrackVersion).where(
                TrackVersion.track_id == track.id, TrackVersion.label == label
            )
        ).scalar_one_or_none()
    )
    if existing is not None:
        return existing
    version = TrackVersion(track_id=track.id, label=label)
    db.add(version)
    db.flush()
    return version


def _find_existing_import(db, provider: str, external_id: str, version_id: str) -> list[str] | None:  # type: ignore[no-untyped-def]
    from sqlalchemy import select

    from app.models import Artifact, SourceRecord

    source = db.execute(
        select(SourceRecord).where(
            SourceRecord.provider == provider,
            SourceRecord.external_id == external_id,
            SourceRecord.track_version_id == version_id,
        )
    ).scalar_one_or_none()
    if source is None:
        return None
    rows = db.execute(
        select(Artifact.id).where(Artifact.source_record_id == source.id)
    ).all()
    return [row[0] for row in rows]


def _decode_content(item: dict[str, Any]) -> bytes | None:
    import base64

    text = item.get("content_text")
    if isinstance(text, str) and text:
        return text.encode("utf-8")
    encoded = item.get("content_base64")
    if isinstance(encoded, str) and encoded:
        try:
            return base64.b64decode(encoded, validate=True)
        except ValueError:
            return None
    return None


def _derive_representations(
    ctx: JobContext,
    version_id: str,
    stored_texts: list[tuple[str, str]],
    profile: dict[str, Any],
    created_by_id: Any,
) -> tuple[list[str], list[str]]:
    import json

    from sqlalchemy import select

    from app.models import Artifact, ArtifactDerivation

    warnings: list[str] = []
    created: list[str] = []
    source_text = "\n".join(text for _, text in stored_texts)
    if not source_text.strip():
        return created, ["nothing to process"]
    input_ids = sorted(artifact_id for artifact_id, _ in stored_texts)
    cached = (
        ctx.db.execute(
            select(ArtifactDerivation).where(
                ArtifactDerivation.input_artifact_ids == input_ids
            )
        )
        .scalars()
        .all()
    )
    profile_json = json.dumps(profile, sort_keys=True)
    for derivation in cached:
        if (
            json.dumps(derivation.profile, sort_keys=True) == profile_json
            and derivation.processor_version == PROCESSOR_VERSION
        ):
            output = ctx.db.get(Artifact, derivation.output_artifact_id)
            if output is not None:
                created.append(output.id)
    if created:
        return created, ["reused cached derivation"]
    outputs = _call_processor(ctx, source_text, profile)
    kinds = {
        "canonical_json": ("canonical_document", "application/json"),
        "lyrics_text": ("lyrics", "text/plain"),
        "lyrics_html": ("rendered_lyrics", "text/html"),
        "chord_chart_html": ("rendered_chord_chart", "text/html"),
    }
    for name, content in outputs.items():
        if name not in kinds:
            continue
        kind, mime = kinds[name]
        data = content.encode("utf-8")
        stored = ctx.store.put(data)
        artifact = Artifact(
            track_version_id=version_id,
            source_record_id=None,
            kind=kind,
            mime_type=mime,
            byte_size=stored.size,
            sha256=stored.sha256,
            object_key=stored.key,
            created_by_id=created_by_id,
        )
        ctx.db.add(artifact)
        ctx.db.flush()
        ctx.db.add(
            ArtifactDerivation(
                output_artifact_id=artifact.id,
                processor_name="processor",
                processor_version=PROCESSOR_VERSION,
                profile=profile,
                input_artifact_ids=input_ids,
            )
        )
        ctx.db.flush()
        created.append(artifact.id)
    return created, warnings


def _call_processor(ctx: JobContext, source_text: str, profile: dict[str, Any]) -> dict[str, str]:
    settings = ctx.settings
    client = httpx.Client(
        base_url=settings.processor_url,
        transport=PROCESSOR_TRANSPORT,
        timeout=settings.processor_timeout_seconds,
        follow_redirects=False,
    )
    with client:
        try:
            response = client.post(
                "/v1/process",
                json={
                    "source_text": source_text,
                    "profile": profile,
                    "title": None,
                    "artist": None,
                },
            )
        except httpx.TimeoutException as exc:
            raise ProviderFailure(f"processor timed out: {exc}") from exc
        except httpx.ConnectError as exc:
            raise ProviderFailure(f"processor unreachable: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderFailure(f"processor http error: {exc}") from exc
    if response.status_code == 429:
        raise RetryLater(
            parse_retry_after_seconds(response.headers.get("retry-after")),
            "processor throttled",
        )
    if response.status_code >= 400:
        code, detail = _error_code_and_detail(response)
        message = f"processor failed ({response.status_code}): {detail}"
        if 400 <= response.status_code < 500:
            raise FatalJobError(message)
        raise ProviderFailure(message)
    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderFailure("processor returned invalid JSON") from exc
    outputs = body.get("outputs", {}) if isinstance(body, dict) else {}
    return {k: v for k, v in outputs.items() if isinstance(v, str)}


def register_online_kinds() -> None:
    from app.jobs.service import JobKind, register_kind

    register_kind(JobKind(name="online.search", handler=handle_online_search))
    register_kind(JobKind(name="online.import", handler=handle_online_import))
