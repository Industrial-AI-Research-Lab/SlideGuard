# SlideGuard Evaluation System

A comprehensive slide deck evaluation system using LangGraph and LangChain that analyzes presentations based on multiple criteria. Features include slide type filtering, presentation type categorization (scientific, technological, collaborative, industrial), and intelligent criteria application based on context.

## Features

- **LangGraph Integration**: Graph-based workflows for orchestrated evaluation tasks
- **LangChain Integration**: LLM interactions and structured outputs
- **CLI Interface**: Command-line interface with Typer
- **Web UI**: Interactive Gradio-based web interface with multi-language support (EN/RU)
- **User Authentication**: Role-based access control (Admin/User/Guest)
- **Slide Type Filtering**: Apply criteria only to specific slide types (e.g., title slides)
- **Presentation Type System**: Support for different presentation types (scientific, technological, collaborative, industrial)
- **Category Organization**: Criteria organized by functional categories
- **Priority-Based Evaluation**: Criteria evaluated in priority order
- **Async Support**: Synchronous and asynchronous evaluation workflows
- **Intelligent Caching**: Caching of evaluation results for faster subsequent runs
- **PDF Report Generation**: Export evaluation results as professional PDF reports
- **vLLM Support**: Compatible with vLLM servers and OpenAI-compatible APIs
- **Langfuse Integration**: Optional observability and tracing support

## Quick Start

### Installation

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install -e .

# Or install dependencies manually
pip install pydantic python-dotenv typer langfuse tqdm gradio PyMuPDF reportlab langchain langchain-openai langgraph pypdfium2 bcrypt
```

### Configuration

Set up your environment variables:

```bash
export SLIDEGUARD_LLM_API_KEY="your-api-key"
export SLIDEGUARD_LLM_API_BASE="http://localhost:8000/v1"
export SLIDEGUARD_LLM_MODEL="/model"

# Optional: Cache directories
export SLIDEGUARD_CACHE_DIR=".slideguard_cache"
export SLIDEGUARD_FILE_CACHE_DIR=".file_cache"

# Or use interactive setup
python3 -m slideguard.setup setup
```

### Basic Usage

```bash
# List available criteria
slideguard eval list-criterias

# Basic evaluation
slideguard eval run --presentation-path presentation.pdf

# With specific criteria
slideguard eval run -p presentation.pdf \
  --criteria slide_visual_arrangement \
  --criteria deck_structure_analysis

# With presentation type filtering
slideguard eval run -p presentation.pdf \
  --presentation-type scientific

# Evaluate in Russian
slideguard eval run -p presentation.pdf --lang ru

# Combine presentation type and language
slideguard eval run -p presentation.pdf \
  --presentation-type technological --lang ru

# Batch processing
slideguard eval multirun --folder-path /path/to/pdfs \
  --presentation-type scientific

# Launch Web UI
slideguard ui run --host 127.0.0.1 --port 7860
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SLIDEGUARD_LLM_API_KEY` | API key for LLM service | **Required** |
| `SLIDEGUARD_LLM_API_BASE` | Base URL for LLM API | **Required** |
| `SLIDEGUARD_LLM_MODEL` | Model name | `/model` |
| `SLIDEGUARD_CACHE_DIR` | Main cache directory | `.slideguard_cache` |
| `SLIDEGUARD_EVALUATIONS_DIR` | Evaluations cache directory | `.slideguard_cache/evaluations` |
| `SLIDEGUARD_FILE_CACHE_DIR` | File cache directory | `.slideguard_cache/file_cache` |
| `SLIDEGUARD_MAX_CONCURRENCY` | Max concurrent LLM requests | `8` (if not set) |
| `AUTH_DB_URL` | Authentication database URL | `sqlite:///./auth.db` |

**Optional Langfuse Configuration** (for observability with `--use-langfuse` flag):
- `LANGFUSE_PUBLIC_KEY` - Langfuse public API key
- `LANGFUSE_SECRET_KEY` - Langfuse secret API key
- `LANGFUSE_HOST` - Langfuse server URL

### Setup Scripts

```bash
poetry run python3 -m slideguard.setup setup    # Interactive setup
poetry run python3 -m slideguard.setup test     # Test installation
poetry run python3 -m slideguard.setup example  # Generate example script
```

## CLI Usage

### Evaluation Commands

```bash
# List all criteria (default: scientific presentation type)
slideguard eval list-criterias

# List criteria for specific presentation type
slideguard eval list-criterias --presentation-type technological

# Basic evaluation with all criteria for presentation type
slideguard eval run -p presentation.pdf --presentation-type scientific

# Specific criteria
slideguard eval run -p presentation.pdf \
  --criteria slide_visual_arrangement \
  --criteria slide_abbreviations \
  --criteria deck_structure_analysis

# Custom output and options
slideguard eval run -p presentation.pdf \
  -o results.json \
  --use-langfuse \
  --max-concurrency 5

# Batch processing multiple PDFs
slideguard eval multirun -f /path/to/pdfs \
  --output-folder results \
  --deck-concurrency 5 \
  --max-concurrency 10

# Evaluate in Russian language
slideguard eval run -p presentation.pdf --lang ru
slideguard eval run -p presentation.pdf -l ru

# Batch processing in Russian
slideguard eval multirun -f /path/to/pdfs --lang ru

# Combine presentation type and language
slideguard eval run -p presentation.pdf \
  --presentation-type technological \
  --lang ru

# Full example with all options
slideguard eval run -p presentation.pdf \
  --presentation-type industrial \
  --lang ru \
  --criteria slide_visual_arrangement \
  --criteria slide_industrial_applicability \
  -o results.json \
  --max-concurrency 8
```

**Language Support**:
- Use `--lang en` or `-l en` for English (default)
- Use `--lang ru` or `-l ru` for Russian
- The language affects all evaluation comments, suggestions, summaries, and recommendations
- Supported languages: `en` (English), `ru` (Russian)

**Presentation Type Support**:
- Use `--presentation-type` or `-t` to specify the type: `scientific` (default), `technological`, `collaborative`, `industrial`
- Each presentation type has specific criteria tailored to its context
- The presentation type filters which criteria are available and applicable
- Use `slideguard eval list-criterias --presentation-type <type>` to see available criteria for each type

**Batch Processing Output** (in specified output folder):
- `evaluations_<filename>.json` - Successful results
- `evaluations_<filename>.error` - Error details (if failed)
- `evaluations_<filename>.stdout` - Standard output logs
- `evaluations_<filename>.stderr` - Standard error logs

### UI Commands

```bash
# Launch UI with default English language
slideguard ui run

# Launch UI with Russian language
slideguard ui run --lang ru
slideguard ui run -l ru

# Full example with all options
slideguard ui run --host 127.0.0.1 --port 7860 --lang ru --theme dark
```

### Admin Commands

```bash
# Create admin user (for Web UI)
slideguard admin create -u admin -r admin

# Manage users
slideguard admin list
slideguard admin pwd -u username
slideguard admin role -u username -r admin
slideguard admin delete -u username
```

## Web UI

### Launch

```bash
# Launch with default English UI
slideguard ui run --host 127.0.0.1 --port 7860

# Launch with Russian UI
slideguard ui run --host 127.0.0.1 --port 7860 --lang ru

# Launch with custom theme
slideguard ui run --host 127.0.0.1 --port 7860 --theme dark

# Combined options
slideguard ui run --host 127.0.0.1 --port 7860 --lang ru --theme dark
```

Access at `http://localhost:7860`

### Features

- **PDF Upload**: Drag and drop or select PDF files
- **User Authentication**: Login system with role-based access (Admin/User/Guest)
- **Criteria Selection**: Choose evaluation criteria with friendly display names
- **Interactive Viewer**: Navigate slides with evaluations
- **Multi-Language Support**: Switch between English and Russian (EN/RU button)
- **PDF Reports**: Generate professional reports in selected language
- **Admin Panel**: User management (visible to admins only)

**Language Support**:
- Set default language at startup with `--lang` flag: `--lang en` (English) or `--lang ru` (Russian)
- Click the EN/RU button in the top-right corner to switch languages dynamically
- All UI elements, evaluation results, and PDF reports are translated
- LLM prompts automatically switch to Russian when Russian is selected
- Criteria friendly names displayed in the selected language

**Service Criteria**: Technical criteria (`slide_type`, `slide_description`) are automatically included when needed for deck-level evaluations.

## Python API

### Basic Example

```python
import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.utils.config import load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager
from slideguard.schemes import Criteria

async def evaluate():
    config = load_config()
    llm = create_llm_from_config(config)
    
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )
    
    # Evaluate with all criteria
    result = await evaluator.evaluate_presentation("presentation.pdf")
    
    # Or with specific criteria
    result = await evaluator.evaluate_presentation(
        presentation_path="presentation.pdf",
        slide_criterias=[
            Criteria.slide_visual_arrangement,
            Criteria.slide_abbreviations
        ],
        deck_criterias=[Criteria.deck_structure_analysis]
    )
    
    print(f"Overall score: {result.overall_score}")
    return result

asyncio.run(evaluate())
```

### Changing Evaluation Language via Python API

The evaluation results language can be controlled through the `ControlledLLM` class. The LLM will generate all comments, suggestions, and summaries in the specified language:

```python
import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.utils.config import load_config
from slideguard.crew.controlled_llm import create_llm_from_config, AppLanguage
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager
from slideguard.schemes import Criteria

async def evaluate_in_russian():
    config = load_config()
    
    # Create LLM with Russian language
    llm = create_llm_from_config(config, language=AppLanguage.RU)
    
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )
    
    result = await evaluator.evaluate_presentation("presentation.pdf")
    print(f"Overall score: {result.overall_score}")
    return result

async def evaluate_and_switch_language():
    config = load_config()
    
    # Start with English
    llm = create_llm_from_config(config, language=AppLanguage.EN)
    
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )
    
    # Evaluate in English
    result_en = await evaluator.evaluate_presentation("presentation_en.pdf")
    
    # Switch to Russian for next evaluation
    llm.set_language(AppLanguage.RU)
    result_ru = await evaluator.evaluate_presentation("presentation_ru.pdf")
    
    return result_en, result_ru

# Run evaluation in Russian
asyncio.run(evaluate_in_russian())
```

**Supported Languages**:
- `AppLanguage.EN` - English (default)
- `AppLanguage.RU` - Russian

**Note**: Language affects:
- All evaluation comments and suggestions
- Summary and TLDR text
- Error messages and recommendations
- The language instructions sent to the LLM

## Available Criteria

### Presentation Types

SlideGuard supports different presentation types, each with specific criteria:
- **Scientific**: Research presentations with focus on scientific novelty
- **Technological**: Technology-focused presentations with practical solutions
- **Collaborative**: Team collaboration and engagement presentations
- **Industrial**: Industry-oriented presentations with real-world applications

Use the `--presentation-type` flag to filter criteria by presentation type:
```bash
slideguard eval run -p presentation.pdf --presentation-type scientific
```

### Slide-Level Criteria

**Service Criteria** (automatically included when needed):
- `slide_type` - Classification of slide types (hidden from UI)
- `slide_description` - Comprehensive slide content analysis (hidden from UI)

**General Evaluation Criteria** (all presentation types):
- `slide_visual_arrangement` - Visual design and layout evaluation
- `slide_abbreviations` - Abbreviations usage and clarity
- `slide_fact_link_availability` - Factual claims and link availability
- `slide_graphic_content_match` - Graphic-content alignment
- `slide_orphography_correctness` - Spelling and grammar
- `slide_title_content_match` - Title-content alignment
- `slide_title_slide_quality` - Title quality (only for title slides)

**Track Justification Criteria** (problem statement slides):
- `slide_track_justification_scientific` - Scientific track justification
- `slide_track_justification_collaborative` - Collaborative track justification
- `slide_track_justification_industrial` - Industrial track justification
- `slide_track_justification_technological` - Technological track justification

**Novelty Criteria**:
- `slide_novelty_scientific` - Scientific novelty presentation quality
- `slide_novelty_technological` - Technological novelty presentation quality

**Related Works Review Criteria** (current state slides):
- `slide_related_works_review_scientific` - Related works review for scientific presentations
- `slide_related_works_review_technological` - Related works comparison for technological presentations
- `slide_related_works_review_collaborative` - Related works comparison for collaborative presentations
- `slide_related_works_review_industrial` - Related works comparison for industrial presentations

**Specialized Content Criteria**:
- `slide_industrial_applicability` - Industrial applicability analysis
- `slide_key_results_scientific` - Key results for scientific presentations
- `slide_key_results_technological` - Key results for technological presentations
- `slide_key_results_collaborative` - Key results for collaborative presentations
- `slide_key_results_industrial` - Key results for industrial presentations

### Deck-Level Criteria

- `deck_structure_analysis` - Overall presentation structure (requires service criteria)
- `deck_storytelling` - Narrative flow and storytelling quality
- `deck_research_quality` - Research methodology and quality

**Note**: Criteria are displayed with friendly names in the Web UI (e.g., "Visual arrangement" / "Визуальное оформление" for `slide_visual_arrangement`). Many criteria are automatically filtered based on slide types and presentation types.

## Architecture

### Core Components

- **SlideGuardEvaluator**: High-level interface using LangGraph workflows
- **Criteria System**: Modular evaluation criteria with type and category support
- **LangGraph StateGraph**: Workflow orchestration for parallel and sequential tasks
- **ControlledLLM**: LangChain-based LLM wrapper with structured output and language control
- **File Manager**: PDF processing and slide extraction
- **Cache Manager**: Intelligent caching of evaluation results

### Evaluation Workflow

1. **Service Criteria**: Slide type classification and description generation
2. **Slide-Level Criteria**: Parallel evaluation of selected criteria for individual slides
3. **Deck-Level Criteria**: Overall presentation structure and quality assessment
4. **Summary Generation**: Comprehensive summary and scoring

## Troubleshooting

### Common Issues

1. **LLM not available**: Set environment variables with `python3 -m slideguard.setup setup`
2. **Import errors**: Install dependencies with `poetry install` or `pip install -e .`
3. **File not found**: Ensure presentation file exists and is accessible
4. **API errors**: Check API key and base URL configuration
5. **CLI not found**: Ensure SlideGuard is installed (`poetry install` or `pip install -e .`)
6. **Evaluator not initialized**: Check configuration and API keys
7. **Admin panel not visible**: Log in as admin user (create with `slideguard admin create -u admin -r admin`)

### Clear Cache

```bash
rm -rf .slideguard_cache
```

### Test Installation

```bash
python3 -m slideguard.setup test
slideguard eval list-criterias
slideguard --help
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
