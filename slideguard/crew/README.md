# SlideGuard Evaluation Engine

This module contains the LangGraph-based evaluation engine used by both the CLI and the Web UI.

## Architecture

### Core components

- `SlideGuardEvaluator`: orchestrates evaluation using a LangGraph `StateGraph`
- Criteria registry:
  - `slideguard/criteria/configs.py`: config definitions (`DEFAULT_CRITERIA_CONFIGS`)
  - `slideguard/criteria/factory.py`: builds `CriteriaRegistry` from configs
  - `slideguard/criteria/base.py`: `CriterionInfo` supports `agent_prompt_template: str | Callable[[Optional[PresentationType]], str]`
- `ControlledLLM`: structured output wrapper with explicit criteria language control (EN/RU)
- `CacheManager`: caches per slide/deck; cache keys include criterion id, presentation type, and criteria language

### Evaluation flow (high level)

1. Service criteria run first when required:
   - `slide_type` (also provides `contains_infographics`)
   - `slide_description`
2. Slide criteria run in parallel (with slide-type/infographics applicability filtering).
3. Deck criteria run (prompt can adapt to selected `PresentationType`).
4. Summary + TL;DR + overall score generation.

## Usage (Python)

```python
import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.criteria import get_registry_provider
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.utils.config import load_config
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager
from slideguard.criteria.presentation_types import PresentationType

async def main():
    config = load_config()
    llm = create_llm_from_config(config)
    provider = get_registry_provider()
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm,
        registry_provider=provider,
    )
    await evaluator.evaluate_presentation(
        presentation_path="path/to/presentation.pdf",
        presentation_type=PresentationType.SCIENTIFIC,
    )

asyncio.run(main())
```