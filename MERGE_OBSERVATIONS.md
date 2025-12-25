# Merge Observations (develop vs rebased branch)

## What `develop` already has (relevant to presentation types)

- **Criteria are config-driven**
  - `slideguard/criteria/configs.py` defines `DEFAULT_CRITERIA_CONFIGS` as a list of `CriterionConfig`.
  - `CriterionConfig` compiles into `CriterionInfo` via `slideguard/criteria/factory.py`.
  - `slideguard/criteria/__init__.py` exposes a cached `CriteriaRegistryProvider`.

- **Applicability filtering exists and is the right layer for presentation-type logic**
  - The registry (`CriteriaRegistry`) is the central point that selects which criteria apply for a given presentation type.

- **Prompts can be presentation-type aware**
  - `CriterionInfo.agent_prompt_template` supports `str` or `Callable[[Optional[PresentationType]], str]`.
  - Deck criteria (`deck_storytelling`, `deck_structure_analysis`, `deck_research_quality`) already support `generate_prompt(presentation_type=...)`.

- **Slide types are managed centrally**
  - `slideguard/criteria/slide_types.py` provides a `SlideTypeManager` and prompt generation from the known slide types.
  - Slide type prompt generation can be filtered by `presentation_type`.

- **Evaluator already propagates selected presentation type**
  - `slideguard/crew/evaluator.py` passes `presentation_type` into `CriterionInfo.to_runnable()` for service + deck criteria.

## What the rebased branch adds / changes

- **New slide criteria (presentation-type-specific)**
  - Adds `slide_track_justification_*` criteria with prompt generator `slideguard/criteria/slide_track_justification.py`.
  - Adds `slide_related_works_review_*` criteria with prompt generator `slideguard/criteria/slide_related_works_review.py`.

- **New postprocessing utilities**
  - Adds `slideguard/criteria/postprocessors.py` with:
    - `filter_sort_by_severity()`
    - `abbreviations_whitelist()`

- **Service output enrichment**
  - `slideguard/schemes.py` expands `SlideType` output with `contains_infographics: bool`.
  - `SlideDescriptionWithType` becomes a composition of `SlideDescription` + `SlideType`.

- **Slide type taxonomy extensions**
  - Adds slide taxonomy entries that are presentation-type-specific (scientific/industrial/collaborative/technological).
  - A dedicated `Scientific Track Justification` slide type was considered but removed; track justification is evaluated on `Problem Statement` slides.

## Conflicts / duplications discovered while rebasing

- **`PresentationType` was duplicated**
  - `slideguard/criteria/types.py` imported `PresentationType` and then redefined another `PresentationType` enum.
  - This would cause inconsistent comparisons, wrong `.value` usage, and unpredictable filtering behavior.

- **Two competing applicability models**
  - One side modeled applicability as enum lists (`applicable_presentation_types`, `exclude_presentation_types`).
  - The other side modeled applicability as string lists (`presentation_types`).

## Resolution direction (high-level)

- **Keep config/registry architecture from `develop`** and integrate only the new useful features.
- **Use one canonical `PresentationType` enum** (`slideguard/criteria/presentation_types.py`).
- **Final decision: keep the enum include/exclude model**
  - Criterion applicability is expressed as:
    - `applicable_presentation_types: Optional[List[PresentationType]]`
    - `exclude_presentation_types: Optional[List[PresentationType]]`
  - UI/CLI are allowed to use strings, but must convert at the boundary via `PresentationType.from_string(...)` before filtering.

## Rebase checkpoint: commit `f25e751` conflict resolution notes (this step)

- **Conflicts resolved in**:
  - `slideguard/criteria/configs.py`
  - `slideguard/criteria/slide_types.py`
  - `slideguard/ui/app.py`

- **Kept (develop architecture)**:
  - `CriterionConfig` + registry provider flow (no per-file `CriterionInfo` singletons reintroduced).
  - Enum-based applicability: `Applicability.applicable_presentation_types=[PresentationType.<TYPE>]`.
  - Deck criteria still use `generate_prompt` functions (presentation-type-aware prompts).

- **Rejected / removed (design drift)**:
  - Any `presentation_types=[...]` field in configs (string-list model).
  - `SlideType.SCIENTIFIC_TRACK_JUSTIFICATION` taxonomy entry (track justification remains evaluated on `SlideType.PROBLEM_STATEMENT` via criteria).

- **Additions kept**:
  - New criteria wiring in `configs.py`: novelty, industrial applicability, key results (all gated via enum presentation types).
  - Slide taxonomy extensions kept as additive: `PUBLICATION_READINESS`, `TECHNOLOGICAL_REALIZATION_LEVEL`, `INDUSTRIAL_POTENTIAL`, `COLLABORATIVE_PROGRESS`, `INDUSTRIAL_APPLICABILITY`, `KEY_RESULTS`.
  - `INDUSTRIAL_APPLICABILITY` slide type is tagged with `presentation_type=PresentationType.INDUSTRIAL`.
  - `KEY_RESULTS` slide type is left generic (no presentation-type restriction).

- **Gotcha fixed during resolution**:
  - `configs.py` temporarily had a duplicated `applicable_presentation_types=` keyword argument inside one `Applicability(...)` block; removed the duplicate and verified compile clean.

