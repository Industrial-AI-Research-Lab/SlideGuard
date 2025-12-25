# Criteria System

SlideGuard criteria are defined via configs and compiled into a registry. This keeps criterion metadata, applicability rules, prompts, schemas, and postprocessing in one consistent pipeline.

## Architecture

### Source of truth

- Criteria ids: `slideguard/schemes.py::Criteria`
- Presentation types: `slideguard/criteria/presentation_types.py::PresentationType`
- Slide taxonomy: `slideguard/criteria/slide_types.py::SlideTypeManager`

### Config → registry pipeline

- `slideguard/criteria/configs.py`
  - Defines `DEFAULT_CRITERIA_CONFIGS: List[CriterionConfig]`
- `slideguard/criteria/factory.py`
  - `CriterionConfig` compiles into `CriterionInfo`
  - `CriteriaRegistryProvider` caches `CriteriaRegistry` instances
- `slideguard/criteria/base.py`
  - `CriterionInfo` defines prompt/schema metadata and supports type-aware prompts:
    - `agent_prompt_template: str | Callable[[Optional[PresentationType]], str]`

## Applicability model (non-negotiable)

Applicability is expressed using enum lists, not strings:

- `Applicability.applicable_presentation_types: Optional[List[PresentationType]]`
- `Applicability.exclude_presentation_types: Optional[List[PresentationType]]`
- `Applicability.applicable_slide_types: Optional[List[str]]`
- `Applicability.exclude_slide_types: Optional[List[str]]`
- `Applicability.requires_infographics: bool`

Filtering happens in the registry (`CriteriaRegistry.get_slide_ids/get_deck_ids`) and at evaluation time for slide-type/infographics applicability.

## Adding a new criterion

1. Add a new enum value to `slideguard/schemes.py::Criteria`.
2. Add the prompt (string or generator) under `slideguard/criteria/`.
3. Add a `CriterionConfig(...)` entry in `slideguard/criteria/configs.py`:
   - set `target` (`slide`/`deck`)
   - set `agent_prompt_template` (string or generator)
   - set `output` schema (`scored_list` or `custom`)
   - set `applicability` using enums for presentation types
4. Run `slideguard eval list-criterias -t <type>` and verify it is reachable.