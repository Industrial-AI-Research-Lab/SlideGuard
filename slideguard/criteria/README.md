# Criteria Info System

This module provides separate pools of criteria for slide-level and deck-level analysis. Each criterion defines a specific aspect of presentation evaluation with its own prompt and schema.

## Criterion Types

- **Slide Criteria**: Analyze individual slides (e.g., content, visual design)
- **Deck Criteria**: Analyze entire presentations (e.g., structure, flow, coherence)

## Architecture

### Core Components

- **`CriterionInfo`**: Base class that holds criterion metadata with type classification
- **Separate Registries**: Slide and deck criteria are managed in separate pools
- **Individual Criterion Files**: Self-contained criterion definitions

### File Structure

```
criteria_info/
├── __init__.py                    # Registry and public API
├── base.py                       # CriterionInfo base class
├── slide_helper_description.py   # Slide description criterion
├── slide_visual_consistency.py   # Visual consistency criterion
├── deck_structure_analysis.py    # Deck structure criterion
└── README.md                     # This file
```

## Usage

### Basic Usage

```python
from slideguard.criteria_info import get_criterion, get_criterion_names

# Get all available criteria
names = get_criterion_names()
print(names)  # ['Slide Description', 'Visual Consistency', 'Deck Structure Analysis']

# Get a specific criterion
criterion = get_criterion("Slide Description")
if criterion:
    print(criterion.criterion_name)
    print(criterion.criterion_type)  # 'slide' or 'deck'
    print(criterion.criterion_prompt)
    print(criterion.criterion_schema)
```

### Advanced Usage - Separate Pools

```python
from slideguard.criteria_info import (
    get_slide_criteria,
    get_deck_criteria,
    get_slide_criterion_names,
    get_deck_criterion_names,
    slide_description,
    slide_visual_consistency,
    deck_structure
)

# Get criteria by type
slide_criteria = get_slide_criteria()
deck_criteria = get_deck_criteria()

# Get criterion names by type
slide_names = get_slide_criterion_names()  # ['Slide Description', 'Visual Consistency']
deck_names = get_deck_criterion_names()    # ['Deck Structure Analysis']

# Direct access to specific criteria
description = slide_description
visual = slide_visual_consistency
structure = deck_structure

# Work with schemas
schema = description.criterion_schema
fields = schema.model_fields
```

### Type-Specific Functions

```python
from slideguard.criteria_info import get_criteria_by_type, get_criterion_names_by_type

# Get criteria by type
slide_criteria = get_criteria_by_type("slide")
deck_criteria = get_criteria_by_type("deck")

# Get names by type
slide_names = get_criterion_names_by_type("slide")
deck_names = get_criterion_names_by_type("deck")
```

## Adding New Criteria

1. Create a new file in the `criteria_info/` directory
2. Define your Pydantic schema
3. Create a `CriterionInfo` instance with appropriate `criterion_type`
4. Import and register it in `__init__.py`

### Example

```python
# my_new_slide_criterion.py
from pydantic import BaseModel, Field
from slideguard.criteria_info.base import CriterionInfo

class MySlideAnalysis(BaseModel):
    score: int = Field(description="Score from 1-10", ge=1, le=10)
    analysis: str = Field(description="Detailed analysis")

my_slide_criterion = CriterionInfo(
    criterion_name="My Slide Analysis",
    criterion_type="slide",  # Specify the type
    criterion_description="Analyze slides for...",
    criterion_prompt="You are an expert...",
    criterion_schema=MySlideAnalysis
)
```

```python
# my_new_deck_criterion.py
from pydantic import BaseModel, Field
from slideguard.criteria_info.base import CriterionInfo

class MyDeckAnalysis(BaseModel):
    score: int = Field(description="Score from 1-10", ge=1, le=10)
    analysis: str = Field(description="Detailed analysis")

my_deck_criterion = CriterionInfo(
    criterion_name="My Deck Analysis",
    criterion_type="deck",  # Specify the type
    criterion_description="Analyze decks for...",
    criterion_prompt="You are an expert...",
    criterion_schema=MyDeckAnalysis
)
```

Then add to `__init__.py`:
```python
from .my_new_slide_criterion import my_slide_criterion
from .my_new_deck_criterion import my_deck_criterion
_register_criterion(my_slide_criterion)
_register_criterion(my_deck_criterion)
```

## API Reference

### Functions

#### General Functions
- `get_criterion(name: str) -> Optional[CriterionInfo]`: Get criterion by name
- `get_all_criteria() -> List[CriterionInfo]`: Get all criteria
- `get_criterion_names() -> List[str]`: Get all criterion names
- `register_criterion(criterion: CriterionInfo) -> None`: Register new criterion
- `unregister_criterion(name: str) -> bool`: Remove criterion

#### Type-Specific Functions
- `get_slide_criteria() -> List[CriterionInfo]`: Get all slide criteria
- `get_deck_criteria() -> List[CriterionInfo]`: Get all deck criteria
- `get_slide_criterion_names() -> List[str]`: Get slide criterion names
- `get_deck_criterion_names() -> List[str]`: Get deck criterion names
- `get_criteria_by_type(type: str) -> List[CriterionInfo]`: Get criteria by type
- `get_criterion_names_by_type(type: str) -> List[str]`: Get names by type

### CriterionInfo Attributes

- `criterion_name: str`: Unique identifier for the criterion
- `criterion_type: str`: Type of criterion ("slide" or "deck")
- `criterion_description: str`: Human-readable description
- `criterion_prompt: str`: LLM prompt for this criterion
- `criterion_schema: BaseModel`: Pydantic schema for structured output

## Benefits of This Approach

1. **Separate Pools**: Slide and deck criteria are organized separately for better clarity
2. **Type Classification**: Each criterion is clearly classified by its scope and purpose
3. **Centralized Registry**: Easy discovery and selection of criteria by type
4. **Type Safety**: Pydantic schemas ensure structured outputs
5. **Extensibility**: Easy to add new criteria without modifying existing code
6. **Separation of Concerns**: Each criterion is self-contained
7. **Consistent Interface**: All criteria follow the same pattern
8. **Easy Testing**: Individual criteria can be tested in isolation
9. **Backward Compatibility**: Existing code continues to work with the combined registry 