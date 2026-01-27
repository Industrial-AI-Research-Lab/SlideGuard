from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from slideguard.metrics.schemas import GoldenYAMLSchema, NormalizedIssue, NormalizedSlideEntry
from slideguard.schemes import Criteria


class YAMLFormatError(Exception):
    pass


def load_normalized_yaml(path: Path) -> GoldenYAMLSchema:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise YAMLFormatError(f"Failed to read {path}") from exc
    if not isinstance(data, dict):
        raise YAMLFormatError("YAML root must be an object")
    deck = _parse_deck(data.get("deck") or {})
    slides = _parse_slides(data.get("slides") or [])
    annotation_status = data.get("annotation_status")
    schema_version = data.get("schema_version", "v1")
    return GoldenYAMLSchema(deck=deck, slides=slides, annotation_status=annotation_status, schema_version=schema_version)


def _parse_deck(payload: Dict[str, Any]) -> Dict[Criteria, List[NormalizedIssue]]:
    result: Dict[Criteria, List[NormalizedIssue]] = {}
    if not isinstance(payload, dict):
        raise YAMLFormatError("Deck section must be a mapping")
    for name, issues in payload.items():
        criterion = _coerce_criterion(name, deck=True)
        normalized = [_coerce_issue(item) for item in _ensure_list(issues)]
        result[criterion] = normalized
    return result


def _parse_slides(items: List[Any]) -> List[NormalizedSlideEntry]:
    result: List[NormalizedSlideEntry] = []
    if not isinstance(items, list):
        raise YAMLFormatError("Slides section must be a list")
    for entry in items:
        if not isinstance(entry, dict):
            raise YAMLFormatError("Slide entry must be a mapping")
        if "slide_id" not in entry or "criteria" not in entry:
            raise YAMLFormatError("Slide entry must include slide_id and criteria")
        slide_id = int(entry["slide_id"])
        criterion = _coerce_criterion(entry["criteria"], deck=False)
        issues = [_coerce_issue(item) for item in _ensure_list(entry.get("issues") or [])]
        result.append(
            NormalizedSlideEntry(
                slide_id=slide_id,
                criteria=criterion,
                issues=issues,
                applicability_override=bool(entry.get("applicability_override", False)),
            )
        )
    return result


def _ensure_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _coerce_issue(value: Any) -> NormalizedIssue:
    if isinstance(value, NormalizedIssue):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            raise YAMLFormatError("Issue text cannot be empty")
        return NormalizedIssue(issue=text)
    if isinstance(value, dict):
        payload = dict(value)
        payload["issue"] = str(payload.get("issue") or payload.get("comment") or "").strip()
        if not payload["issue"]:
            raise YAMLFormatError("Issue entry missing issue text")
        if "severity" in payload:
            payload["severity"] = int(payload["severity"])
        return NormalizedIssue(**payload)
    raise YAMLFormatError("Unsupported issue entry")


def _coerce_criterion(value: Any, deck: bool) -> Criteria:
    if isinstance(value, Criteria):
        return value
    try:
        criterion = Criteria(str(value))
    except ValueError as exc:
        raise YAMLFormatError(f"Unknown criterion {value}") from exc
    if deck and not criterion.is_deck_criteria():
        raise YAMLFormatError(f"{criterion.value} is not deck-level")
    if not deck and not criterion.is_slide_criteria():
        raise YAMLFormatError(f"{criterion.value} is not slide-level")
    return criterion







