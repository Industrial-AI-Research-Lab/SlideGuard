# Slide Type Extension Guide

This guide shows you how to conveniently extend slide types in SlideGuard using the new management system.

## Quick Start

### Basic Extension

```python
from slideguard.criteria.slide_types import add_slide_type

# Add a new slide type
add_slide_type(
    name="Methodology",
    description="Slide describing the research methodology or approach used",
    category="content"
)
```

### Advanced Extension with Aliases and Metadata

```python
from slideguard.criteria.slide_types import slide_type_manager

slide_type_manager.add_slide_type(
    name="Literature Review",
    description="Slide summarizing relevant literature and research background",
    category="content",
    aliases=["Lit Review", "Background", "Related Work"],
    metadata={
        "requires_citations": True,
        "typical_position": "early",
        "complexity": "medium"
    }
)
```

## Available Methods

### Adding Slide Types

```python
# Simple addition
add_slide_type(name, description, category="general")

# Advanced addition with manager
slide_type_manager.add_slide_type(
    name, description, category, aliases, metadata
)
```

### Querying Slide Types

```python
from slideguard.criteria.slide_types import (
    get_slide_types, 
    get_slide_types_by_category,
    validate_slide_type
)

# Get all slide types
all_types = get_slide_types()

# Get slide types by category
content_types = get_slide_types_by_category("content")

# Validate a slide type
is_valid = validate_slide_type("Goal")
```

### Working with Categories

```python
# Get all available categories
categories = slide_type_manager.get_categories()

# Get slide types by category
content_types = slide_type_manager.get_slide_types_by_category("content")
```

### Aliases and Metadata

```python
# Find slide type by alias
slide_type = slide_type_manager.find_slide_type_by_alias("Lit Review")

# Get slide types with aliases
types_with_aliases = slide_type_manager.get_slide_types_with_aliases()

# Get slide type information
info = slide_type_manager.get_slide_type_info("Literature Review")
print(f"Description: {info.description}")
print(f"Category: {info.category}")
print(f"Aliases: {info.aliases}")
print(f"Metadata: {info.metadata}")
```

## Import/Export Functionality

### Export to JSON

```python
# Export to string
json_data = slide_type_manager.export_to_json()

# Export to file
slide_type_manager.export_to_json("slide_types.json")
```

### Import from JSON

```python
json_data = '''
{
    "Appendix": {
        "description": "Additional supporting material",
        "category": "supplementary",
        "aliases": ["Supporting Material", "Extra Info"],
        "metadata": {"optional": true}
    }
}
'''

imported_count = slide_type_manager.import_from_json(json_data)
```

## Integration with Criteria

### Using New Slide Types in Criteria

```python
from slideguard.criteria.base import CriterionInfo
from slideguard.criteria.slide_types import add_slide_type

# First, add your new slide type
add_slide_type("Demo", "Live demonstration slide", category="interactive")

# Then use it in your criterion
my_criterion = CriterionInfo(
    criterion_name="My Custom Criterion",
    criterion_type="slide",
    criterion_description="My custom analysis",
    criterion_prompt="Analyze the slide...",
    criterion_schema=MySchema,
    applicable_slide_types=["Demo", "Goal"],  # Use your new slide type
    category="custom"
)
```

### Filtering Criteria by Slide Types

```python
from slideguard.criteria import get_criteria_for_slide_types

# Get criteria applicable to your new slide type
demo_criteria = get_criteria_for_slide_types(["Demo"])
```

## Best Practices

### 1. Use Descriptive Names
```python
# Good
add_slide_type("Literature Review", "Slide summarizing relevant literature...")

# Avoid
add_slide_type("Lit", "Literature stuff...")
```

### 2. Choose Appropriate Categories
- `content`: Information-heavy slides
- `structure`: Organizational slides
- `technical`: Technical details and specifications
- `interactive`: Q&A, demos, etc.
- `academic`: References, citations, etc.

### 3. Use Aliases for Flexibility
```python
add_slide_type(
    name="Experimental Results",
    description="Results from experiments",
    aliases=["Results", "Findings", "Data"]
)
```

### 4. Add Metadata for Advanced Features
```python
add_slide_type(
    name="Methodology",
    description="Research methodology",
    metadata={
        "requires_diagrams": True,
        "typical_position": "middle",
        "complexity": "high"
    }
)
```

## Example: Complete Extension Workflow

```python
from slideguard.criteria.slide_types import add_slide_type, slide_type_manager
from slideguard.criteria.base import CriterionInfo

# 1. Add new slide types
add_slide_type("Methodology", "Research methodology description", category="content")
add_slide_type("Q&A", "Question and answer session", category="interactive")

# 2. Create a criterion that uses the new slide type
class MethodologyAnalysis(BaseModel):
    methodology_score: int = Field(description="Methodology quality score", ge=1, le=5)
    suggestions: List[str] = Field(description="Improvement suggestions")

methodology_criterion = CriterionInfo(
    criterion_name="Methodology Analysis",
    criterion_type="slide",
    criterion_description="Analyze methodology slides",
    criterion_prompt="Evaluate the methodology presentation...",
    criterion_schema=MethodologyAnalysis,
    applicable_slide_types=["Methodology"],  # Use your new slide type
    category="content"
)

# 3. Register the criterion
from slideguard.criteria import register_criterion
register_criterion(methodology_criterion)

# 4. Use it in evaluations
from slideguard.criteria import get_criteria_for_slide_types
methodology_criteria = get_criteria_for_slide_types(["Methodology"])
```

## Troubleshooting

### Common Issues

1. **Slide type already exists**: Use `slide_type_manager.get_slide_type_info()` to check if it exists first.

2. **Invalid slide type in criteria**: Use `validate_slide_type()` to verify before using in criteria.

3. **Category not found**: Use `slide_type_manager.get_categories()` to see available categories.

### Validation

```python
# Check if slide type exists
if not validate_slide_type("My New Type"):
    print("Slide type doesn't exist")

# Check if category exists
if "my_category" not in slide_type_manager.get_categories():
    print("Category doesn't exist")
```

## Migration from Old System

If you were previously using hardcoded slide type lists, you can now use the dynamic system:

```python
# Old way (still works for backward compatibility)
SLIDE_TYPES = ["Title slide", "Goal", "Conclusion"]

# New way (recommended)
from slideguard.criteria.slide_types import get_slide_types
slide_types = get_slide_types()  # Gets all registered types dynamically
```

This new system makes it much easier to extend and manage slide types in SlideGuard!
