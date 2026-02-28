# SlideGuard Architecture

## Overview

SlideGuard is an AI-powered slide deck evaluation system built on **LangGraph** and **LangChain**. It analyzes PDF presentations against a configurable set of criteria at both the individual slide level and the overall deck level, producing structured feedback, scores, and PDF reports.

The system supports multiple presentation types (scientific, industrial, collaborative, technological), multi-language output (EN/RU), and exposes functionality through a CLI, a Gradio-based web UI, and a Python API.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Entry Points                        │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │   CLI    │  │  Gradio UI   │  │    Python API     │  │
│  │ (Typer)  │  │ (app.py)     │  │ (SlideGuardEval.) │  │
│  └────┬─────┘  └──────┬───────┘  └────────┬──────────┘  │
│       │               │                   │             │
│       └───────────────┼───────────────────┘             │
│                       ▼                                 │
│           ┌───────────────────────┐                     │
│           │  SlideGuardEvaluator  │                     │
│           │  (crew/evaluator.py)  │                     │
│           └───────────┬───────────┘                     │
│                       │                                 │
│        ┌──────────────┼──────────────┐                  │
│        ▼              ▼              ▼                  │
│  ┌───────────┐ ┌────────────┐ ┌────────────┐           │
│  │ LangGraph │ │ Criteria   │ │ Controlled │           │
│  │ Workflows │ │ Registry   │ │ LLM        │           │
│  └───────────┘ └────────────┘ └────────────┘           │
│        │              │              │                  │
│        ▼              ▼              ▼                  │
│  ┌───────────┐ ┌────────────┐ ┌────────────┐           │
│  │   File    │ │   Cache    │ │ LangChain  │           │
│  │  Manager  │ │  Manager   │ │ + OpenAI   │           │
│  └───────────┘ └────────────┘ └────────────┘           │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
SlideGuard/
├── slideguard/                 # Main Python package
│   ├── main.py                 # CLI entrypoint (Typer app)
│   ├── schemes.py              # Pydantic data models (shared types)
│   ├── setup.py                # Interactive setup / test scripts
│   ├── crew/                   # Evaluation engine
│   │   ├── evaluator.py        # SlideGuardEvaluator — LangGraph orchestration
│   │   ├── controlled_llm.py   # ControlledLLM — LLM wrapper with retries
│   │   ├── summary_processor.py# Summary / scoring logic
│   │   └── callbacks.py        # Langfuse observability callbacks
│   ├── criteria/               # Criteria definitions and registry
│   │   ├── base.py             # CriterionInfo, BaseAttributes
│   │   ├── factory.py          # CriterionConfig, CriteriaRegistry, Provider
│   │   ├── configs.py          # All default criterion configurations
│   │   ├── types.py            # Shared types (CriteriaTarget, OutputSpec, …)
│   │   ├── presentation_types.py # PresentationType enum
│   │   ├── slide_types.py      # SlideType enum and SlideTypeManager
│   │   ├── postprocessors.py   # Result post-processing functions
│   │   └── slide_*.py / deck_*.py  # Per-criterion prompt definitions
│   ├── ui/                     # Web interface
│   │   ├── app.py              # Gradio application (create_app)
│   │   ├── auth.py             # SQLAlchemy/bcrypt authentication
│   │   ├── translations.py     # EN/RU translation strings
│   │   ├── report_generator.py # PDF report generation (ReportLab)
│   │   ├── launch.py           # Standalone launcher script
│   │   └── demo.py             # Demo mode
│   └── utils/                  # Shared utilities
│       ├── config.py           # SlideGuardConfig, env loading
│       ├── file_manager.py     # PDF → PNG extraction and caching
│       ├── cache_manager.py    # Evaluation result caching (pickle)
│       └── base.py             # Common base utilities
├── examples/                   # Example scripts
├── resources/                  # Golden datasets, notebooks, slide decks
├── data/                       # Test PDFs and evaluation samples
├── docs/                       # Documentation
├── pyproject.toml              # Poetry project definition
└── .env                        # Environment configuration (not committed)
```

## Core Components

### 1. SlideGuardEvaluator (`crew/evaluator.py`)

The central orchestration engine. It builds a **LangGraph `StateGraph`** that coordinates the full evaluation pipeline. The graph is assembled dynamically based on which criteria are selected.

**Graph structure:**

```
process_presentation
        │
        ├── slide_type (service)
        ├── slide_description (service)
        │
        ├── slide_flow (subgraph)
        │   ├── criterion_1 ─┐
        │   ├── criterion_2 ─┤  (parallel)
        │   ├── criterion_N ─┘
        │   └── gather_slide_results
        │
        ├── deck_flow (subgraph, if deck criteria selected)
        │   ├── build_deck_descriptions
        │   ├── deck_criterion_1 ─┐
        │   ├── deck_criterion_N ─┘  (parallel)
        │   └── gather_deck_results
        │
        └── summary_flow (subgraph)
            ├── build_summary
            ├── build_tldr
            └── compute_overall
```

Key behaviors:
- **Service criteria** (`slide_type`, `slide_description`) always run first — they produce metadata consumed by downstream criteria and deck-level analysis.
- **Slide-level criteria** run in parallel per-criterion. Each criterion is evaluated on all applicable slides (filtered by slide type, presentation type, and infographics requirements).
- **Deck-level criteria** operate on aggregated slide descriptions and run in parallel after service criteria complete.
- **Summary flow** runs last, generating a natural-language summary, TL;DR, and overall score.

**State management** uses `EvaluationState`, a Pydantic model with annotated merge functions (`_merge_dicts`, `_merge_lists`, `_take_any`) that LangGraph uses to combine outputs from parallel branches.

### 2. Criteria System (`criteria/`)

The criteria system is config-driven and extensible.

**Core abstractions:**

| Class | Purpose |
|---|---|
| `CriterionConfig` | Declarative criterion definition (prompt, output shape, applicability rules) |
| `CriterionInfo` | Runtime representation built from config; creates LangChain runnables |
| `CriteriaRegistry` | Indexed collection of `CriterionInfo` instances; supports filtering by presentation type |
| `CriteriaRegistryProvider` | Factory that builds registries with optional per-user overrides; uses caching |

**Output models** are generated dynamically via Pydantic's `create_model`. Most criteria use `OutputKind.scored_list`, which auto-generates a model containing:
- A list of items (each with severity, element, suggestion fields)
- An overall score (1–5)

Service criteria use `OutputKind.custom` with hand-written Pydantic models (`SlideType`, `SlideDescription`).

**Applicability filtering** — each criterion can declare:
- `applicable_slide_types` / `exclude_slide_types` — which slide types it applies to
- `applicable_presentation_types` / `exclude_presentation_types` — which presentation types it applies to
- `requires_infographics` — only apply when the slide contains infographic content

**Post-processors** (`postprocessors.py`) are functions applied to results after LLM evaluation: severity filtering/sorting, abbreviation whitelisting, and combining duplicate abbreviation findings.

### 3. ControlledLLM (`crew/controlled_llm.py`)

A wrapper around LangChain's `ChatOpenAI` that adds:

- **Structured output with retries** — uses `PydanticOutputParser` + `RetryWithErrorOutputParser` for robust JSON extraction from LLM responses. Falls back through multiple parsing strategies.
- **Image support** — `_ensure_image_messages` detects `` ```image path``` `` markers in prompts and converts them to base64 multi-modal messages.
- **Language control** — injects language instructions (EN/RU) into every prompt to control output language.
- **vLLM compatibility** — `LegacyCompatibleChatOpenAI` subclass remaps `max_completion_tokens` → `max_tokens` for non-OpenAI API servers.
- **Text cleaning** — pre-processes LLM output to handle Unicode edge cases and malformed JSON escapes.

### 4. File Manager (`utils/file_manager.py`)

Handles PDF → PNG conversion using `pypdfium2`. Features:
- Content-hash-based caching — files are hashed (SHA-256), and extracted images are reused if the hash matches a prior run.
- Each slide is rendered at 1024×768 resolution and stored as a JPEG-encoded PNG.
- Returns a `SlideDeckImages` object with ordered slide paths.

### 5. Cache Manager (`utils/cache_manager.py`)

Generic async cache for evaluation results, keyed by:
- Deck name (presentation file path)
- Criteria ID (includes presentation type and language suffix)
- Slide ID (or `None` for deck-level criteria)
- Content hash of the input (slide image path or deck description)

Values are serialized with `pickle`. Fallback results (from failed evaluations) are not cached, ensuring automatic retries on next run.

### 6. Summary Processor (`crew/summary_processor.py`)

Transforms raw evaluation results into payloads for LLM-based summary generation:

- **Basic mode** — filters low-severity items per slide, removes non-applicable criteria.
- **Advanced mode** — adds navigation metadata: slide type distribution, severity histograms, prioritized problem lists, and identified strengths.
- **Overall score** — weighted average of all criterion scores across slides and deck.
- **Dynamic thresholds** — severity thresholds adapt based on the distribution of findings in the current evaluation (if <10% items are severe, thresholds lower automatically).

## Data Flow

```
PDF file
  │
  ▼
FileManager.process_presentation()
  │ (PDF → PNG slides, cached by content hash)
  ▼
EvaluationState (initial)
  │
  ▼
LangGraph StateGraph execution:
  │
  ├─ process_presentation → SlideDeckImages
  │
  ├─ service criteria (parallel)
  │   ├─ slide_type → List[SlideType]      (per slide)
  │   └─ slide_description → List[SlideDescription]
  │
  ├─ slide_flow (parallel per criterion)
  │   Each criterion:
  │     1. Check applicability (slide type / infographics filter)
  │     2. Build filtered subset of slides
  │     3. Check cache → compute missing via LLM
  │     4. Apply post-processors
  │     5. Merge results into state
  │   └─ gather_slide_results → List[SlideEvaluationResult]
  │
  ├─ deck_flow (parallel per criterion)
  │   1. Build DeckDescription from slide descriptions
  │   2. Each deck criterion evaluated via LLM (cached)
  │   └─ gather_deck_results → DeckEvaluationResult
  │
  └─ summary_flow (sequential)
      1. SummaryProcessor → payload
      2. LLM → Summary text
      3. LLM → TL;DR
      4. Calculate overall score
  │
  ▼
FullEvaluation (returned to caller)
```

## Entry Points

### CLI (`main.py`)

Built with **Typer**, providing three command groups:

| Command | Description |
|---|---|
| `slideguard eval run` | Evaluate a single PDF |
| `slideguard eval multirun` | Batch-evaluate a folder of PDFs (with concurrency control) |
| `slideguard eval list-criterias` | List available criteria for a presentation type |
| `slideguard ui run` | Launch the Gradio web interface |
| `slideguard admin create/pwd/role/delete/list` | User management for the web UI |

Registered as a console script via `pyproject.toml`: `slideguard = "slideguard.main:main"`.

### Web UI (`ui/app.py`)

A **Gradio Blocks** application providing:

- PDF upload and slide viewer with navigation
- Presentation type selection (filters available criteria dynamically)
- Criteria checkboxes with localized friendly names
- Per-run criteria language selection (EN/RU)
- Real-time evaluation with progress status
- Slide-by-slide results display with expandable details
- PDF report generation and download
- Admin panel for user management (role-gated)
- Authentication via SQLAlchemy + bcrypt (`auth.py`)
- Full UI localization through `Translator` class (`translations.py`)

### Python API

Direct programmatic access via `SlideGuardEvaluator`:

```python
evaluator = SlideGuardEvaluator(
    file_manager=FileManager(...),
    cache_manager=CacheManager(...),
    llm=create_llm_from_config(config),
    registry_provider=get_registry_provider(),
)
result = await evaluator.evaluate_presentation("presentation.pdf")
```

## Data Models (`schemes.py`)

| Model | Description |
|---|---|
| `Criteria` | Enum of all criterion identifiers (slide_* and deck_*) |
| `SlideImage` | Slide reference with image path and slide ID |
| `SlideDeckImages` | Collection of slides for a presentation |
| `SlideDescription` | LLM-generated slide title, description, summary |
| `SlideType` | Slide type classification and infographics flag |
| `SlideDescriptionWithType` | Combined description + type (used for deck input) |
| `DeckDescription` | Serialized deck-level context from all slide descriptions |
| `SlideEvaluationResult` | Per-slide results: type, description, and per-criterion evaluations |
| `DeckEvaluationResult` | Deck-level criterion results |
| `FullEvaluation` | Complete output: slide evaluations, deck evaluations, summary, TL;DR, score |
| `UIEvaluationResult` | UI-specific result container for Gradio rendering |

## Configuration

Environment-based configuration via `.env` or environment variables:

| Variable | Purpose |
|---|---|
| `SLIDEGUARD_LLM_API_KEY` | LLM service API key |
| `SLIDEGUARD_LLM_API_BASE` | LLM API base URL |
| `SLIDEGUARD_LLM_MODEL` | Model identifier (default: `/model`) |
| `SLIDEGUARD_CACHE_DIR` | Root cache directory |
| `SLIDEGUARD_FILE_CACHE_DIR` | PDF-to-PNG file cache |
| `SLIDEGUARD_MAX_CONCURRENCY` | Max parallel LLM requests |
| `OPENAI_API_KEY` | Optional direct OpenAI key (bypasses vLLM config) |
| `AUTH_DB_URL` | SQLAlchemy database URL for user auth |

The system auto-detects whether to use legacy `max_tokens` (for vLLM/compatible servers) vs `max_completion_tokens` (for OpenAI) based on the base URL host.

## Observability

Optional **Langfuse** integration for tracing LLM calls. The `ImageStrippingLangfuseHandler` callback redacts base64 image data from traces to prevent bloating the Langfuse dashboard while preserving full request/response tracing.

## Key Design Decisions

- **LangGraph over sequential execution** — enables parallel evaluation of independent criteria within a single graph invocation, with clear dependency ordering.
- **Config-driven criteria** — new criteria are added by appending a `CriterionConfig` to `configs.py`; no evaluator code changes needed.
- **Dynamic Pydantic models** — output schemas are generated at registry build time via `create_model`, keeping criterion definitions declarative.
- **Two-level caching** — file cache (PDF → PNG) and evaluation cache (criterion results) operate independently, allowing cache reuse even when criteria sets change.
- **Fallback resilience** — every LLM call has fallback handling; failed evaluations produce sentinel `FallbackResult` objects that are excluded from caching and clearly marked in outputs.
- **Multi-modal prompts** — slide images are embedded as base64 in LangChain messages via a custom prompt preprocessor, supporting any OpenAI-compatible vision API.
