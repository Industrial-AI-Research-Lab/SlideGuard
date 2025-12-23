## Key merge decisions (keep for future rebases)

### Presentation types: single source of truth

- **Canonical enum**: `slideguard/criteria/presentation_types.py::PresentationType`
- Never define another `PresentationType` enum elsewhere.

### Applicability filtering model (type-safe)

- Use enum lists, not strings:
  - `Applicability.applicable_presentation_types: Optional[List[PresentationType]]`
  - `Applicability.exclude_presentation_types: Optional[List[PresentationType]]`
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

### Security rule

- Never commit local test scripts containing tokens/keys (e.g. `tmp_test.py`).
- Prefer environment variables for notebook / local evaluation credentials.

