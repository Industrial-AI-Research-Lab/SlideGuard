from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml
from Levenshtein import distance as levenshtein_distance

from slideguard.criteria import get_registry_provider
from slideguard.schemes import Criteria
from slideguard.metrics.schemas import GoldenYAMLSchema, NormalizedIssue, NormalizedSlideEntry


def convert_directory(source: Path, destination: Optional[Path], dry_run: bool) -> None:
    provider = get_registry_provider()
    registry = provider.get_for_user()
    slide_criteria = set(registry.get_slide_ids())
    deck_criteria = set(registry.get_deck_ids())
    target_dir = destination or source
    target_dir.mkdir(parents=True, exist_ok=True)
    for yaml_path in sorted(source.glob("*.yaml")):
        normalized = _parse_legacy_yaml(yaml_path, slide_criteria, deck_criteria)
        if dry_run:
            print(f"[dry-run] {yaml_path} -> {target_dir / yaml_path.name}")
            continue
        out_path = target_dir / yaml_path.name
        payload = normalized.model_dump(mode="json")
        with out_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=True)
        print(f"Converted {yaml_path} -> {out_path}")


def _parse_legacy_yaml(
    yaml_path: Path,
    slide_criteria: Iterable[Criteria],
    deck_criteria: Iterable[Criteria],
) -> GoldenYAMLSchema:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{yaml_path} is not a mapping")
    evaluation = data.get("evaluation") or {}
    deck = _parse_deck(evaluation.get("deck"), deck_criteria)
    slides = _parse_slides(evaluation.get("slides"), slide_criteria)
    return GoldenYAMLSchema(deck=deck, slides=slides, annotation_status=data.get("annotation_status"))


def _parse_deck(payload: Any, criteria_pool: Iterable[Criteria]) -> Dict[Criteria, List[NormalizedIssue]]:
    result: Dict[Criteria, List[NormalizedIssue]] = {}
    if not payload:
        return result
    if not isinstance(payload, dict):
        raise ValueError("Deck section must be a mapping")
    for name, issues in payload.items():
        criterion = _resolve_criterion(name, criteria_pool)
        normalized = _normalize_issues(issues)
        if normalized:
            result.setdefault(criterion, []).extend(normalized)
    return result


def _parse_slides(payload: Any, criteria_pool: Iterable[Criteria]) -> List[NormalizedSlideEntry]:
    result: List[NormalizedSlideEntry] = []
    if not payload:
        return result
    if not isinstance(payload, list):
        raise ValueError("Slides section must be a list")
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each slide entry must be a mapping")
        slide_id = int(entry.get("slide_id"))
        criterion_name = entry.get("criteria") or entry.get("criterion")
        criterion = _resolve_criterion(criterion_name, criteria_pool)
        issues_payload = entry.get("issues") or entry.get("issue") or entry.get("comment") or entry.get("comments")
        normalized = _normalize_issues(issues_payload)
        result.append(
            NormalizedSlideEntry(
                slide_id=slide_id,
                criteria=criterion,
                issues=normalized,
                applicability_override=bool(entry.get("applicability_override", False)),
            )
        )
    return result


def _normalize_issues(payload: Any) -> List[NormalizedIssue]:
    if payload is None:
        return []
    if isinstance(payload, list):
        items: List[NormalizedIssue] = []
        for item in payload:
            items.extend(_normalize_issues(item))
        return items
    if isinstance(payload, str):
        text = payload.strip()
        return [NormalizedIssue(issue=text)] if text else []
    if isinstance(payload, dict):
        issue = str(payload.get("issue") or payload.get("comment") or "").strip()
        if not issue:
            return []
        severity = int(payload.get("severity", 1))
        severity = min(max(severity, 1), 3)
        return [NormalizedIssue(issue=issue, severity=severity, suggestion=payload.get("suggestion"))]
    raise ValueError("Unsupported issue entry")


def _resolve_criterion(name: Any, pool: Iterable[Criteria]) -> Criteria:
    try:
        return Criteria(str(name))
    except ValueError:
        normalized = str(name).lower().strip()
        candidates = list(pool)
        best = None
        best_distance = 999
        for candidate in candidates:
            distance = levenshtein_distance(normalized, candidate.value)
            if distance < best_distance:
                best = candidate
                best_distance = distance
        if best is None or best_distance > 3:
            raise ValueError(f"Unknown criterion {name}")
        return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert legacy SlideGuard YAMLs to normalized format.")
    parser.add_argument("--source", type=Path, default=Path("resources/golden"), help="Folder with legacy YAML files")
    parser.add_argument("--destination", type=Path, help="Folder for converted files (defaults to source)")
    parser.add_argument("--dry-run", action="store_true", help="Print planned conversions without writing files")
    args = parser.parse_args()
    convert_directory(args.source, args.destination, args.dry_run)


if __name__ == "__main__":
    main()







