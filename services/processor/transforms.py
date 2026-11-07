"""Safe, registry-gated transformations over canonical documents.

Every step is validated against a registry (unknown steps and bad configs
are rejected, never executed). Chord propagation is conservative: ambiguous
repeats produce warnings and leave the music untouched.
"""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .chords import transpose_chord


class NormalizeSectionsConfig(BaseModel):
    pass


class ExpandRepeatedChordsConfig(BaseModel):
    strategy: str = Field(default="matching_sections", pattern="^(matching_sections)$")
    on_ambiguity: str = Field(default="warn", pattern="^(warn|skip)$")


class TransposeConfig(BaseModel):
    semitones: int = Field(ge=-11, le=11)
    accidentals: str = Field(default="prefer_sharps", pattern="^(prefer_sharps|prefer_flats)$")


_STEP_CONFIGS: dict[str, type[BaseModel]] = {
    "normalize_sections": NormalizeSectionsConfig,
    "expand_repeated_chords": ExpandRepeatedChordsConfig,
    "transpose": TransposeConfig,
}

_STEP_ORDER = ("normalize_sections", "expand_repeated_chords", "transpose")


def validate_profile(profile: dict) -> list[str]:
    """Return a list of human-readable errors (empty when valid)."""
    from .models import ProcessingProfile

    errors: list[str] = []
    try:
        parsed = ProcessingProfile.model_validate(profile)
    except ValidationError as exc:
        return [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
    seen: set[str] = set()
    for step in parsed.steps:
        if step.type not in _STEP_CONFIGS:
            errors.append(f"unknown step: {step.type}")
            continue
        if step.type in seen:
            errors.append(f"duplicate step: {step.type}")
            continue
        seen.add(step.type)
        try:
            _STEP_CONFIGS[step.type].model_validate(step.config)
        except ValidationError as exc:
            errors.extend(
                f"{step.type}.{'.'.join(map(str, e['loc']))}: {e['msg']}"
                for e in exc.errors()
            )
    order = [step.type for step in parsed.steps if step.type in _STEP_ORDER]
    if order != sorted(order, key=_STEP_ORDER.index):
        errors.append(f"steps must run in order: {', '.join(_STEP_ORDER)}")
    return errors


def apply_profile(document: dict, profile: dict) -> tuple[dict, list[str]]:
    warnings: list[str] = []
    working = deepcopy(document)
    for step in profile.get("steps", []):
        step_type = step.get("type")
        config = step.get("config", {})
        if step_type == "normalize_sections":
            _normalize_sections(working, warnings)
        elif step_type == "expand_repeated_chords":
            _expand_repeated_chords(working, config, warnings)
        elif step_type == "transpose":
            _transpose(working, config, warnings)
        else:
            warnings.append(f"skipped unknown step: {step_type}")
    return working, warnings


def _normalize_sections(document: dict, warnings: list[str]) -> None:
    ids: set[str] = set()
    for position, section in enumerate(document.get("sections", [])):
        original = section.get("id") or f"section-{position + 1}"
        candidate = original
        suffix = 1
        while candidate in ids:
            suffix += 1
            candidate = f"{original}-{suffix}"
        if candidate != section.get("id"):
            warnings.append(f"renamed duplicate section id {section.get('id')!r} to {candidate!r}")
        section["id"] = candidate
        ids.add(candidate)
        for line in section.get("lines", []):
            line["chords"] = sorted(line.get("chords", []), key=lambda c: c["position"])
            width = len(line.get("lyrics", ""))
            for placement in line["chords"]:
                placement["position"] = max(0, min(placement["position"], width))


def _expand_repeated_chords(document: dict, config: dict[str, Any], warnings: list[str]) -> None:
    if config.get("strategy", "matching_sections") != "matching_sections":
        warnings.append("unsupported expand strategy; skipped")
        return
    by_id = {section["id"]: section for section in document.get("sections", [])}
    for section in document.get("sections", []):
        target_id = section.get("repeat_of")
        if not target_id:
            continue
        target = by_id.get(target_id)
        if target is None or target is section:
            warnings.append(
                f"section {section.get('label')!r} repeats unknown section; left unchanged"
            )
            continue
        own_chords = sum(len(line.get("chords", [])) for line in section.get("lines", []))
        if own_chords:
            warnings.append(
                f"section {section.get('label')!r} already has chords; repeat not expanded"
            )
            continue
        if len(section.get("lines", [])) != len(target.get("lines", [])):
            warnings.append(
                f"section {section.get('label')!r} has a different line count than "
                f"{target.get('label')!r}; chords not propagated"
            )
            continue
        if target.get("tablature") and not section.get("tablature"):
            warnings.append(
                f"tablature is never propagated to {section.get('label')!r}; kept opaque"
            )
        for own_line, target_line in zip(section["lines"], target["lines"], strict=True):
            own_line["chords"] = deepcopy(target_line.get("chords", []))
        section["repeat_of"] = None


def _transpose(document: dict, config: dict[str, Any], warnings: list[str]) -> None:
    semitones = int(config.get("semitones", 0))
    prefer_flats = config.get("accidentals", "prefer_sharps") == "prefer_flats"
    for section in document.get("sections", []):
        for line in section.get("lines", []):
            for placement in line.get("chords", []):
                transposed = transpose_chord(placement["chord"], semitones, prefer_flats)
                if transposed is None:
                    warnings.append(
                        f"could not transpose {placement['chord']!r}; left unchanged"
                    )
                    continue
                placement["chord"] = transposed
    if semitones:
        key = document.get("musical_key")
        if key:
            transposed_key = transpose_chord(key, semitones, prefer_flats)
            if transposed_key is None:
                warnings.append(f"could not transpose key {key!r}; left unchanged")
            else:
                document["musical_key"] = transposed_key


def registered_steps() -> list[str]:
    return sorted(_STEP_CONFIGS)
