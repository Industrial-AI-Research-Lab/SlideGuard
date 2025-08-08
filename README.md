# SlideGuard Crew-Based Evaluation System

A comprehensive slide deck evaluation system using CrewAI agents that analyzes presentations based on multiple criteria with support for slide type filtering and categorization.

## Features

- **CrewAI Integration**: Uses specialized AI agents for different evaluation tasks
- **Slide Type Filtering**: Apply criteria only to specific slide types
- **Category Organization**: Criteria organized by functional categories (visual, content, structure, etc.)
- **Priority-Based Evaluation**: Criteria evaluated in priority order
- **Async Support**: Both synchronous and asynchronous evaluation workflows
- **Intelligent Caching**: Caching of evaluation results and file processing
- **Environment Configuration**: Easy setup via environment variables
- **vLLM Support**: Compatible with vLLM servers and other OpenAI-compatible APIs

## Quick Start

### 1. Installation

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install pydantic crewai openai python-dotenv

# Optional: Install additional dependencies for full functionality
pip install langchain-community pypdfium2 requests tiktoken pillow
```

### 2. Configuration

Set up your environment variables for LLM access:

```bash
# For vLLM server
export SLIDEGUARD_LLM_API_KEY="your-api-key"
export SLIDEGUARD_LLM_API_BASE="http://localhost:8000/v1"
export SLIDEGUARD_LLM_MODEL="/model"

# Or use the interactive setup
python -m slideguard.setup setup
```

### 3. Basic Usage

```python
import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator

async def main():
    # Initialize evaluator (uses environment variables automatically)
    evaluator = SlideGuardEvaluator()
    
    # Evaluate a presentation
    result = await evaluator.evaluate_presentation("presentation.pdf")
    
    print(f"Overall score: {result.overall_score}")
    print(f"Summary: {result.summary}")

# Run the evaluation
asyncio.run(main())
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLIDEGUARD_LLM_API_KEY` | API key for LLM service | Required |
| `SLIDEGUARD_LLM_API_BASE` | Base URL for LLM API | Required |
| `SLIDEGUARD_LLM_MODEL` | Model name | `/model` |
| `SLIDEGUARD_CACHE_DIR` | Cache directory | `.slideguard_cache` |
| `SLIDEGUARD_FILE_CACHE_DIR` | File cache directory | `.file_cache` |

### Setup Scripts

```bash
# Interactive setup
python -m slideguard.setup setup

# Test installation
python -m slideguard.setup test

# Create example script
python -m slideguard.setup example

# Run all setup steps
python -m slideguard.setup all
```

## Usage Examples

### Basic Evaluation

```python
from slideguard.crew.evaluator import SlideGuardEvaluator

evaluator = SlideGuardEvaluator()
result = await evaluator.evaluate_presentation("presentation.pdf")
```

### Filtered Evaluation

```python
# Evaluate with specific criteria and slide types
result = await evaluator.evaluate_presentation(
    "presentation.pdf",
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
visual_criterion_names = [c.criterion_name for c in visual_criteria]

# Evaluate only visual aspects
result = await evaluator.evaluate_presentation(
    "presentation.pdf",
    slide_criteria=visual_criterion_names
)
```

### Synchronous Evaluation

```python
from slideguard.crew.evaluator import evaluate_presentation_sync

result = evaluate_presentation_sync("presentation.pdf")
```

## Available Criteria

### Slide-Level Criteria

- **Slide Description**: Comprehensive slide content analysis
- **Slide Visual Arrangement**: Visual design and readability evaluation
- **Slide Type**: Classification of slide types
- **Slide Color Analysis**: Color theory and accessibility evaluation
- **Slide Content Quality**: Content clarity and effectiveness evaluation

### Deck-Level Criteria

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

## Testing

```bash
# Run basic structure tests
poetry run python -m slideguard.simple_test

# Run comprehensive tests (requires dependencies)
poetry run python -m slideguard.test_crew_system

# Test installation and configuration
poetry run python -m slideguard.setup test
```

## Examples

See the `examples/` directory for complete usage examples:

- `examples/criteria_eval.py` - Basic evaluation examples
- `slideguard/example_usage.py` - Comprehensive usage patterns

## Troubleshooting

### Common Issues

1. **LLM not available**: Set environment variables or provide LLM instance
2. **Import errors**: Install required dependencies
3. **File not found**: Ensure presentation file exists and is accessible
4. **API errors**: Check API key and base URL configuration

### Debug Mode

```python
# Enable debug output
evaluator = SlideGuardEvaluator()
evaluator.print_status()  # Shows configuration status
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
