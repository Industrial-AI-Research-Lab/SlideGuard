## Key merge decisions (keep for future rebases)

### Presentation types: single source of truth

- **Canonical enum**: `slideguard/criteria/presentation_types.py::PresentationType`
- Never define another `PresentationType` enum elsewhere.

### Applicability filtering model (type-safe)

- Use enum lists, not strings:
  - `Applicability.applicable_presentation_types: Optional[List[PresentationType]]`
  - `Applicability.exclude_presentation_types: Optional[List[PresentationType]]`
- Do not introduce alternative config fields like `presentation_types` (string lists).
- Registry filtering uses enums:
  - `CriteriaRegistry.get_slide_ids(..., presentation_type: Optional[PresentationType])`
  - `CriteriaRegistry.get_deck_ids(..., presentation_type: Optional[PresentationType])`

### UI/CLI boundary rule

- UI and CLI can keep presentation type as **string** for widgets/flags.
- Convert at the boundary:
  - `PresentationType.from_string(value)` before calling registry filtering.

### Criteria system architecture

- Keep the config/registry architecture:
  - `DEFAULT_CRITERIA_CONFIGS` → `CriteriaRegistryProvider` → `CriteriaRegistry`
- Do not reintroduce direct per-file `CriterionInfo` singletons for each criterion.

### Track justification + slide taxonomy decision

- Evaluate track justification via `slide_track_justification_*` on `SlideType.PROBLEM_STATEMENT`.
- Do not keep a dedicated `SCIENTIFIC_TRACK_JUSTIFICATION` slide type.
- Do not keep `slide_scientific_track_justification.py`; it is redundant with `slide_track_justification.py`.

### Security rule

- Never commit local test scripts containing tokens/keys (e.g. `tmp_test.py`).
- Prefer environment variables for notebook / local evaluation credentials.

