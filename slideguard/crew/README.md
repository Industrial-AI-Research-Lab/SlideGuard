# SlideGuard Crew-Based Evaluation System

This module provides a comprehensive slide deck evaluation system using CrewAI agents. The system evaluates presentations based on multiple criteria, with support for slide type filtering and categorization.

## Overview

The crew-based evaluation system consists of:

1. **Specialized Agents**: Each agent focuses on a specific aspect of slide evaluation
2. **Criteria System**: Modular criteria that can be applied based on slide types and categories
3. **Workflow Orchestration**: Coordinated evaluation process using CrewAI
4. **Caching**: Efficient caching of evaluation results
5. **Flexible Filtering**: Support for filtering by slide types and criteria categories

## Architecture

### Core Components

- **SlideGuardAgents**: Main class managing the crew of evaluation agents
- **SlideGuardEvaluator**: High-level interface for presentation evaluation
- **Criteria System**: Modular evaluation criteria with type and category support
- **File Management**: Integration with existing file processing system

### Agent Types

1. **Slide Type Classifier**: Determines the type of each slide
2. **Slide Description Specialist**: Creates detailed slide descriptions
3. **Visual Design Evaluator**: Evaluates visual arrangement and readability
4. **Presentation Structure Analyst**: Evaluates overall deck structure
5. **Evaluation Summary Coordinator**: Creates comprehensive summaries
6. **Custom Criterion Specialists**: Specialized agents for specific criteria

## Usage

### Basic Evaluation

```python
from slideguard.crew.evaluator import SlideGuardEvaluator

# Initialize evaluator
evaluator = SlideGuardEvaluator(llm=your_llm_instance)

# Evaluate presentation
result = await evaluator.evaluate_presentation(
    presentation_path="path/to/presentation.pdf"
)

print(f"Overall score: {result.overall_score}")
print(f"Summary: {result.summary}")
```

### Filtered Evaluation

```python
# Evaluate with specific criteria and slide types
result = await evaluator.evaluate_presentation(
    presentation_path="path/to/presentation.pdf",
    slide_criteria=["Slide Visual Arrangement", "Slide Color Analysis"],
    deck_criteria=["Deck Structure Analysis"],
    slide_types_filter=["goals", "experimental_results"]
)
```

### Category-Based Evaluation

```python
from slideguard.criteria import get_criteria_by_category

# Get criteria by category
visual_criteria = get_criteria_by_category("visual")
content_criteria = get_criteria_by_category("content")

# Evaluate only visual aspects
visual_criterion_names = [c.criterion_name for c in visual_criteria]
result = await evaluator.evaluate_presentation(
    presentation_path="path/to/presentation.pdf",
    slide_criteria=visual_criterion_names
)
```

## Criteria System

### Available Criteria

#### Slide-Level Criteria
- **Slide Description**: Comprehensive slide content analysis
- **Slide Visual Arrangement**: Visual design and readability evaluation
- **Slide Type**: Classification of slide types
- **Slide Color Analysis**: Color theory and accessibility evaluation
- **Slide Content Quality**: Content clarity and effectiveness evaluation

#### Deck-Level Criteria
- **Deck Structure Analysis**: Overall presentation structure evaluation

### Criteria Categories

- **visual**: Visual design and layout criteria
- **content**: Content quality and clarity criteria
- **structure**: Structural organization criteria
- **technical**: Technical aspects criteria
- **accessibility**: Accessibility and usability criteria
- **general**: General evaluation criteria

### Slide Types

- **title**: Title slides
- **separator**: Section separator slides
- **motivation**: Motivation slides
- **goals**: Goals slides
- **tasks**: Tasks slides
- **current_state**: Current state slides
- **proposed_solution**: Proposed solution slides
- **experiment_settings**: Experiment settings slides
- **experimental_results**: Experimental results slides
- **conclusion**: Conclusion slides

## Creating Custom Criteria

```python
from slideguard.criteria.base import CriterionInfo
from pydantic import BaseModel, Field

# Define custom schema
class CustomResult(BaseModel):
    score: int = Field(description="Score from 1 to 5", ge=1, le=5)
    feedback: str = Field(description="Custom feedback")

# Create custom criterion
custom_criterion = CriterionInfo(
    criterion_name="Custom Analysis",
    criterion_type="slide",
    criterion_description="Custom analysis description",
    criterion_prompt="Custom analysis prompt...",
    criterion_schema=CustomResult,
    applicable_slide_types=["goals", "conclusion"],
    priority=3,
    requires_slide_type=True,
    category="custom"
)

# Register the criterion
from slideguard.criteria import register_criterion
register_criterion(custom_criterion)
```

## Advanced Features

### Priority-Based Evaluation

Criteria are evaluated in priority order (lower number = higher priority):
- Priority 1: Essential criteria (slide type, description)
- Priority 2: Important criteria (visual arrangement, content quality)
- Priority 3+: Specialized criteria (color analysis, etc.)

### Slide Type Filtering

Criteria can be filtered based on slide types:
- Some criteria apply to all slide types (`applicable_slide_types=None`)
- Others are specific to certain slide types
- This allows for context-appropriate evaluation

### Caching

The system includes intelligent caching:
- File processing results are cached
- Evaluation results are cached based on parameters
- Cache keys include criteria and slide type filters

### Async Support

The system supports both synchronous and asynchronous evaluation:
- `evaluate_presentation_sync()` for simple use cases
- `evaluate_presentation()` for advanced async workflows

## Integration with Existing System

The crew-based evaluation system integrates seamlessly with the existing SlideGuard infrastructure:

- Uses existing `FileManager` for presentation processing
- Leverages existing `CacheManager` for result caching
- Compatible with existing criteria definitions
- Extends the current evaluation capabilities

## Performance Considerations

- **Parallel Processing**: CrewAI enables parallel evaluation of different criteria
- **Caching**: Intelligent caching reduces redundant processing
- **Selective Evaluation**: Filtering allows evaluation of only relevant criteria
- **Async Operations**: Non-blocking evaluation for better performance

## Error Handling

The system includes robust error handling:
- Graceful degradation when criteria fail
- Detailed error logging
- Fallback mechanisms for missing data
- Validation of evaluation results

## Future Enhancements

- **Dynamic Agent Creation**: Automatic agent creation for new criteria
- **Learning Capabilities**: Agents that learn from evaluation patterns
- **Multi-Modal Support**: Support for video and audio analysis
- **Real-time Evaluation**: Live evaluation during presentation creation
- **Collaborative Evaluation**: Multi-agent collaboration for complex evaluations 