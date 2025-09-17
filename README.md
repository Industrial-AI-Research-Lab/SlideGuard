# SlideGuard Crew-Based Evaluation System

A comprehensive slide deck evaluation system using CrewAI agents that analyzes presentations based on multiple criteria with support for slide type filtering and categorization.

## Features

- **CrewAI Integration**: Uses specialized AI agents for different evaluation tasks
- **CLI Interface**: Easy-to-use command-line interface with Typer
- **Slide Type Filtering**: Apply criteria only to specific slide types
- **Category Organization**: Criteria organized by functional categories (visual, content, structure, etc.)
- **Priority-Based Evaluation**: Criteria evaluated in priority order
- **Async Support**: Both synchronous and asynchronous evaluation workflows
- **Intelligent Caching**: Caching of evaluation results and file processing
- **Environment Configuration**: Easy setup via environment variables
- **vLLM Support**: Compatible with vLLM servers and other OpenAI-compatible APIs
- **Langfuse Integration**: Optional observability and tracing support

## Quick Start

### 1. Installation

```bash
# Using Poetry (recommended)
poetry install

# Or using pip - install core dependencies
pip install pydantic crewai python-dotenv typer langfuse
pip install langchain-openai langchain-community
pip install duckduckgo-search openinference-instrumentation-crewai openinference-instrumentation-litellm
```

### 2. Configuration

Set up your environment variables for LLM access:

```bash
# For vLLM server or OpenAI-compatible API
export SLIDEGUARD_LLM_API_KEY="your-api-key"
export SLIDEGUARD_LLM_API_BASE="http://localhost:8000/v1"
export SLIDEGUARD_LLM_MODEL="/model"

# Optional: Cache directories
export SLIDEGUARD_CACHE_DIR=".slideguard_cache"
export SLIDEGUARD_FILE_CACHE_DIR=".file_cache"

# Or use the interactive setup
python -m slideguard.setup setup
```

### 3. Basic Usage

#### Command Line Interface (Recommended)

```bash
# List all available criteria
slideguard eval list-criterias

# Basic evaluation using CLI
slideguard eval run --presentation-path presentation.pdf

# With custom output file
slideguard eval run -p presentation.pdf -o results.json

# With specific criteria
slideguard eval run -p presentation.pdf \
  --criteria slide_visual_arrangement \
  --criteria deck_structure_analysis

# With Langfuse observability
slideguard eval run -p presentation.pdf --use-langfuse

# With custom concurrency limit
slideguard eval run -p presentation.pdf --max-concurrency 5

# Batch processing multiple PDFs
slideguard eval multirun --folder-path /path/to/pdf/folder

# With custom output folder and deck concurrency
slideguard eval multirun -f /path/to/pdf/folder \
  --output-folder my_results \
  --deck-concurrency 5 \
  --criteria slide_visual_arrangement \
  --criteria deck_structure_analysis
```

#### Python API Usage

```python
import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.utils.config import load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager

async def main():
    # Load configuration
    config = load_config()
    llm = create_llm_from_config(config)
    
    # Initialize evaluator with dependencies
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )
    
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

### CLI Examples

#### Discovering Available Criteria

```bash
# List all available evaluation criteria
slideguard eval list-criterias

# Output shows:
# 📊 Slide-Level Criteria: (10 criteria)
# 📋 Deck-Level Criteria: (3 criteria)
# Plus usage examples
```

#### Running Evaluations

```bash
# Basic evaluation - all criteria
slideguard eval run --presentation-path presentation.pdf

# Specific slide criteria only
slideguard eval run -p presentation.pdf \
  --criteria slide_visual_arrangement \
  --criteria slide_color_and_fonts

# Mix of slide and deck criteria
slideguard eval run -p presentation.pdf \
  --criteria slide_visual_arrangement \
  --criteria deck_structure_analysis \
  --criteria deck_storytelling

# With custom output and observability
slideguard eval run -p presentation.pdf \
  -o detailed_results.json \
  --use-langfuse \
  --max-concurrency 3
```

#### Batch Processing Multiple PDFs

The `multirun` command allows you to process multiple PDF files in a folder concurrently:

```bash
# Basic batch processing - all PDFs in folder
slideguard eval multirun --folder-path /path/to/presentations/

# With custom output folder and concurrency
slideguard eval multirun -f /path/to/presentations/ \
  --output-folder evaluation_results \
  --deck-concurrency 5 \
  --criteria slide_visual_arrangement \
  --criteria deck_structure_analysis \
  --max-concurrency 10

# With observability and custom output location
slideguard eval multirun -f /path/to/presentations/ \
  --output-folder results_2024 \
  --use-langfuse \
  --deck-concurrency 3
```

**Output Files (in specified output folder):**
- `evaluations_<filename>.json` - Successful evaluation results
- `evaluations_<filename>.error` - Error details for failed evaluations  
- `evaluations_<filename>.log` - Captured stdout/stderr logs

**Features:**
- Recursive PDF discovery in the specified folder
- Configurable output folder (defaults to `multirun_results`)
- Concurrent processing with configurable limits
- Individual error handling per PDF
- Progress tracking with visual progress bar
- Comprehensive logging and error reporting
```

### Python API Examples

#### Basic Evaluation

```python
import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator
from slideguard.utils.config import load_config
from slideguard.crew.controlled_llm import create_llm_from_config
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager

async def basic_evaluation():
    config = load_config()
    llm = create_llm_from_config(config)
    
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )
    
    result = await evaluator.evaluate_presentation("presentation.pdf")
    return result

asyncio.run(basic_evaluation())
```

#### Filtered Evaluation

```python
from slideguard.schemes import Criteria

async def filtered_evaluation():
    # Setup evaluator (same as above)
    config = load_config()
    llm = create_llm_from_config(config)
    evaluator = SlideGuardEvaluator(
        file_manager=FileManager(config.file_cache_dir),
        cache_manager=CacheManager(config.evaluations_cache_dir),
        llm=llm
    )
    
    # Evaluate with specific criteria
    result = await evaluator.evaluate_presentation(
        presentation_path="presentation.pdf",
        slide_criterias=[
            Criteria.slide_visual_arrangement,
            Criteria.slide_color_and_fonts
        ],
        deck_criterias=[
            Criteria.deck_structure_analysis
        ]
    )
    return result
```

## Web UI

SlideGuard includes a Gradio-based web interface for interactive presentation evaluation.

### Features

- **PDF Upload**: Drag and drop or select PDF files for evaluation
- **Criteria Selection**: Choose which evaluation criteria to apply
- **Deck-Level Results**: View overall presentation evaluation results
- **Slide-Level Results**: See detailed feedback for each individual slide
- **Interactive Presentation Viewer**: Navigate through slides with corresponding evaluations

### Installation

Install UI-specific dependencies:

```bash
# Using Poetry (recommended)
poetry install

# Or using pip
pip install -r requirements-ui.txt
```

### Running the UI

Launch the UI via the unified CLI:

```bash
# Using the unified CLI (recommended)
slideguard ui run --host 127.0.0.1 --port 7860

# Or via module execution
python -m slideguard.main ui run --host 127.0.0.1 --port 7860

# From Python
python -c "from slideguard.ui.app import create_app; create_app().launch(server_name='127.0.0.1', server_port=7860)"
```

The UI will be available at `http://localhost:7860`

### UI Components

1. **Upload Section**: Drag and drop or select a PDF file to upload
2. **Criteria Selection**: Check/uncheck the criteria you want to evaluate
3. **Results Tabs**:
   - **Deck-Level Results**: Overall presentation evaluation
   - **Slide-Level Results**: Detailed slide-by-slide feedback
   - **Interactive Presentation Viewer**: Navigate slides with evaluations

### Navigation

In the Interactive Presentation Viewer:
- Use the "Previous" and "Next" buttons to navigate between slides
- The current slide number is displayed
- Slide evaluations appear below the slide image
- All slide images are extracted from the PDF for easy viewing

### Configuration

Before using the UI, make sure you have configured your environment variables or `.env` file with the necessary API keys and settings. See the Configuration section above for details.

### Troubleshooting

**Common UI Issues:**

1. **"Evaluator not initialized"**: Check your configuration and API keys
2. **PDF processing errors**: Ensure the PDF file is valid and not corrupted
3. **Missing dependencies**: Install required packages with `pip install gradio PyMuPDF`

**Demo and Testing:**

```bash
# Verify CLI is available
slideguard ui run --help

# Quick local run
slideguard ui run

# Check if UI can be imported
python -c "from slideguard.ui.app import create_app; print('UI ready')"
```

## Admin CLI

Manage users and roles via the unified CLI:

```bash
# Create a user (interactive password prompts)
slideguard admin create -u alice -r user

# Change password
slideguard admin pwd -u alice

# Change role
slideguard admin role -u alice -r admin

# List users
slideguard admin list

# Delete user
slideguard admin delete -u alice
```

## Available Criteria

### Slide-Level Criteria

- **`slide_type`**: Classification of slide types (title, motivation, goals, etc.)
- **`slide_description`**: Comprehensive slide content analysis and description
- **`slide_visual_arrangement`**: Visual design and layout evaluation
- **`slide_color_and_fonts`**: Color theory, font choices, and visual consistency analysis
- **`slide_abbreviations`**: Analysis of abbreviations usage and clarity
- **`slide_fact_link_availability`**: Evaluation of factual claims and link availability
- **`slide_graphic_content_match`**: Assessment of graphic-content alignment
- **`slide_orphography_correctness`**: Spelling and grammar correctness evaluation
- **`slide_title_content_match`**: Analysis of title-content alignment
- **`slide_title_slide_quality`**: Overall slide title quality assessment

### Deck-Level Criteria

- **`deck_structure_analysis`**: Overall presentation structure and flow evaluation
- **`deck_storytelling`**: Narrative flow and storytelling quality assessment
- **`deck_research_quality`**: Research methodology and quality evaluation

### Using Criteria in Commands

```bash
# Use criteria by their enum names
slideguard eval run -p presentation.pdf \
  --criteria slide_visual_arrangement \
  --criteria slide_color_and_fonts \
  --criteria deck_structure_analysis

# Multiple criteria can be specified
slideguard eval run -p presentation.pdf \
  --criteria slide_type \
  --criteria slide_description \
  --criteria deck_storytelling \
  --criteria deck_research_quality
```

### Using Criteria in Python

```python
from slideguard.schemes import Criteria

# Reference criteria by enum values
slide_criterias = [
    Criteria.slide_visual_arrangement,
    Criteria.slide_color_and_fonts,
    Criteria.slide_abbreviations
]

deck_criterias = [
    Criteria.deck_structure_analysis,
    Criteria.deck_storytelling
]

result = await evaluator.evaluate_presentation(
    presentation_path="presentation.pdf",
    slide_criterias=slide_criterias,
    deck_criterias=deck_criterias
)
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
# Test installation and configuration
python -m slideguard.setup test

# Test CLI functionality
slideguard eval run --help

# Run a test evaluation (requires a sample PDF)
slideguard eval run -p sample.pdf -o test_results.json
```

## Examples

See the `examples/` directory for complete usage examples:

- `examples/dynamic_prompt_example.py` - Dynamic prompt usage patterns
- Use `python -m slideguard.setup example` to generate a sample evaluation script

## Main.py Direct Usage

You can also run the main.py file directly:

```bash
# List available criteria
python -m slideguard.main eval list-criterias

# Direct execution
python -m slideguard.main eval run --presentation-path presentation.pdf

# Or if installed via Poetry
poetry run python -m slideguard.main eval run -p presentation.pdf

# With all options
python -m slideguard.main eval run \
  --presentation-path presentation.pdf \
  --output-path results.json \
  --criteria slide_visual_arrangement \
  --criteria deck_structure_analysis \
  --max-concurrency 3 \
  --use-langfuse
```

## Troubleshooting

### Common Issues

1. **LLM not available**: Set environment variables using `python -m slideguard.setup setup`
2. **Import errors**: Install required dependencies with `poetry install` or pip
3. **File not found**: Ensure presentation file exists and is accessible
4. **API errors**: Check API key and base URL configuration
5. **CLI not found**: Ensure SlideGuard is installed (`poetry install` or `pip install -e .`)

### Debug and Configuration Check

```bash
# Check configuration status
python -m slideguard.setup test

# List available evaluation criteria
slideguard eval list-criterias

# Get help for CLI commands
slideguard --help
slideguard eval --help
slideguard eval run --help
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
