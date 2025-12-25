# Merge Plan (rebased branch -> develop)

## Goals

- Preserve `develop`’s existing criteria registry/config architecture and UI integration.
- Merge in new, valuable functionality from the rebased branch without duplicating older/worse implementations.
- Ensure `PresentationType` is a single source of truth and is used consistently across:
  - UI selection / filtering
  - criteria registry selection
  - prompt generation (type-aware prompts)

## Decisions

- **Canonical PresentationType**: `slideguard/criteria/presentation_types.py`
  - All other modules import this (directly or via `slideguard/criteria/types.py` re-export).
- **Applicability representation**: use enum include/exclude lists everywhere
  - `Applicability.applicable_presentation_types: Optional[List[PresentationType]]`
  - `Applicability.exclude_presentation_types: Optional[List[PresentationType]]`
  - Registry filtering uses `PresentationType` values (type-safe).
  - UI/CLI may keep strings, but must convert at the boundary using `PresentationType.from_string(...)`.
- **Prompt typing**: keep `CriterionInfo.agent_prompt_template` as `str | Callable[[Optional[PresentationType]], str]`
  - Deck criteria should use `generate_prompt` so they can adapt to the selected `PresentationType`.

## Conflict resolution strategy by file

### `slideguard/criteria/types.py`

- Remove the duplicate `PresentationType` definition.
- Keep `ALL_PRESENTATION_TYPES` and `DEFAULT_PRESENTATION_TYPE` derived from canonical `PresentationType`.
- Keep `Applicability.applicable_presentation_types` and `Applicability.exclude_presentation_types` and remove string-list alternatives.

### `slideguard/criteria/base.py`

- Keep `CriterionInfo.applicable_presentation_types` / `CriterionInfo.exclude_presentation_types`.
- Do not reintroduce a second string-based filtering model.

### `slideguard/criteria/factory.py`

- Map `CriterionConfig.applicability.applicable_presentation_types` / `exclude_presentation_types` into `CriterionInfo`.
- Keep `CriteriaRegistry.get_slide_ids/get_deck_ids` filtering by `PresentationType`.

### `slideguard/criteria/slide_types.py`

- Keep all slide types, including presentation-type-specific taxonomy.
- Ensure presentation-type-specific slide types are tagged with `presentation_type=PresentationType.<TYPE>`.

### `slideguard/criteria/configs.py`

- Keep deck criteria prompt generators (`generate_prompt`) so prompts remain presentation-type aware.
- Integrate track justification + related works criteria using prompt generators:
  - `slide_track_justification_*` apply to `SlideType.PROBLEM_STATEMENT` and are restricted by `applicable_presentation_types=[PresentationType.<TYPE>]`
  - `slide_related_works_review_*` apply to `SlideType.CURRENT_STATE` and are restricted by `applicable_presentation_types=[PresentationType.<TYPE>]`
- Do not use string-list fields like `presentation_types` in configs; the registry/applicability model is enum-based.

### `slideguard/ui/app.py`

- Import `PresentationType` and `DEFAULT_PRESENTATION_TYPE` from `slideguard/criteria/types.py`.
- Keep UI state as a string (`current_presentation_type`) for UI/serialization.
- Convert string → enum at the boundary (`PresentationType.from_string`) before filtering in registry.
- Convert the evaluation-time dropdown value into `PresentationType` enum for evaluator prompt adaptation.

## After conflicts are resolved

- Stage the 5 formerly-conflicted files and continue the rebase.
- During later rebase commits, resolve any follow-up conflicts using the same rules:
  - prefer `develop`’s architecture
  - accept new features only when they improve behavior or add missing capability
  - reject duplicate/older pathways

## Rebase checkpoint notes (for next commits)

- If any future conflict reintroduces `presentation_types=[...]` in `configs.py`, always convert it into `Applicability.applicable_presentation_types=[PresentationType.<TYPE>]`.
- Slide type taxonomy is allowed to grow, but do not add a `SCIENTIFIC_TRACK_JUSTIFICATION` slide type; use the existing `slide_track_justification_*` criteria applied to `SlideType.PROBLEM_STATEMENT`.
- When resolving UI conflicts, keep all expected translation keys used by the UI (e.g., both `presentation_type_*` and `criteria_language_label`) and avoid removing one side’s keys.

## Safety checks

- Remove any local test scripts containing keys/tokens from version control.
- Run a repo-wide check for conflict markers and obvious secret patterns before finishing.

