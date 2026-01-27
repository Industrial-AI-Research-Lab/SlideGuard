# SlideGuard Metrics, Feedback, and Observability – Full Development Plan

## Overview and Goals

- **Goal**: Add a metrics and feedback pipeline to SlideGuard that evaluates existing model outputs against golden YAML annotations, converts human feedback into YAML, and exposes these workflows via CLI, with Langfuse observability and clear future hooks for UI feedback collection.
- **Constraints**:
  - Integrate cleanly with current components: `SlideGuardEvaluator`, criteria registry, CLI (`slideguard/main.py`), config (`slideguard/utils/config.py`), and UI (`slideguard/ui/app.py`).
  - Keep implementation minimal and focused: batch metrics, YAML parsing, feedback→YAML structures, Langfuse integration, and clear extension points for UI-driven feedback and `eval_pairs` maintenance.

## 1. Existing System Overview (Anchor Points)

- **Evaluator and schemas**
  - `slideguard/crew/evaluator.py`: `SlideGuardEvaluator` runs slide/deck criteria using LangGraph and returns `FullEvaluation` from `slideguard/schemes.py`.
  - `FullEvaluation` contains `slide_evaluations: list[SlideEvaluationResult] `and optional `deck_evaluations: DeckEvaluationResult` with per-criterion outputs, plus summary/score.
  - `Criteria` enum in `slideguard/schemes.py` defines all slide and deck criteria and helper methods `is_slide_criteria`, `is_deck_criteria`, `is_service_criteria`.
  - `criteria/types.py` defines `CriterionResult` and `CriterionResultItem` protocols, which expose `evaluation_results` and `score` for many criteria outputs.

- **Configuration and CLI**
  - `slideguard/utils/config.py`: `SlideGuardConfig`, `load_config`, and `load_langfuse_client` centralize environment config and Langfuse client creation.
  - `slideguard/main.py`: Typer CLI with `eval` (run/multirun), `ui`, and `admin` sub-apps. It already wires config, LLM (`create_llm_from_config`), evaluator, and optional Langfuse for evaluation.

- **UI and criteria registry**
  - `slideguard/ui/app.py`: Gradio UI wraps `SlideGuardEvaluator` for interactive use.
  - `slideguard/criteria/configs.py` and `slideguard/criteria` package: criteria registry and configs used by registry provider (`slideguard/criteria/__init__.py`) consumed by evaluator and CLI.

These building blocks must remain the single source of truth. The metrics and feedback modules will depend on them but must not reimplement core evaluation logic.

## 2. Metrics Package Architecture

Create a new package `slideguard/metrics/` with focused modules:

- `slideguard/metrics/__init__.py`
  - Re-export public types:
    - `EvalPair`, `EvalBatchReport`, `MetricScores`, `CriterionMetrics` from `schemas.py`.
    - `YAMLParser` from `yaml_parser.py`.
    - `EvalPairsManager` from `eval_pairs.py`.
    - `EvaluationMetrics` from `evaluation_metrics.py`.
    - `FeedbackHandler` from `feedback_handler.py`.
    - `metrics_trace` from `observability.py`.

- `slideguard/metrics/schemas.py`
  - Pydantic models for:
    - **Golden YAML**:
      - `NormalizedIssue`: `{ issue: str, severity: int (1–3), suggestion: Optional[str] }`.
      - `NormalizedSlideEntry`: `{ slide_id: int, criteria: Criteria, issues: list[NormalizedIssue], applicability_override: bool = False }`.
      - `NormalizedDeckEntry`: `{ criteria: Criteria, issues: list[NormalizedIssue] }`.
      - `GoldenYAMLSchema`: `{ deck: dict[Criteria, list[NormalizedIssue]], slides: list[NormalizedSlideEntry], annotation_status: Optional[str], schema_version: str }`.
    - **Eval pairs** (`resources/eval_pairs.json`):
      - `EvalPair`: `{ presentation_path: str, metric_yaml_path: str, criteria_preset: str = "default", enabled: bool = True, tags: list[str], notes: Optional[str] }`.
      - `EvalPairsConfig`: root `{ pairs: list[EvalPair], last_updated: Optional[str] }`.
    - **Batch evaluation and metrics**:
      - `FailedEvaluation`: details of failed evaluations (path, error type/message, traceback, retry count, timestamp).
      - `ConfusionEntry`: `{ presentation: str, slide_id: Optional[int], criterion: Criteria, predicted: bool, ground_truth: bool, label: str, predicted_issues: list[str], ground_truth_issues: list[str], reason: str }`.
      - `MetricScores`: `{ tp, fp, fn, tn, precision, recall, f1, accuracy }`.
      - `CriterionMetrics`: `{ criterion: Criteria, slide_metrics: Optional[MetricScores], deck_metrics: Optional[MetricScores] }`.
      - `EvalBatchReport`: `{ run_id: str, timestamp: datetime, evaluator_version: str, config_hash: str, criteria_registry_hash: str, total_presentations: int, successful: int, failed: int, failed_presentations: list[FailedEvaluation], per_criterion_metrics: list[CriterionMetrics], macro_avg_metrics: MetricScores, micro_avg_metrics: MetricScores }`.
      - `EvaluationCheckpoint`: `{ run_id: str, completed_indices: list[int], failed_indices: list[int], timestamp: datetime }`.
    - **Feedback**:
      - `AtomicIssue`: `{ criterion: Criteria, slide_ids: list[int], issue_text: str, confidence: float, needs_review: bool }`.
      - `FeedbackEntry`: structured feedback log line `{ feedback_id: str, feedback_text: str, presentation_path: Optional[str], slide_id: Optional[int], criterion: Optional[Criteria], agreement: Optional[bool], comment: Optional[str], source: str, needs_review: bool, timestamp: datetime, user_id: Optional[str], feedback_hash: Optional[str] }`.
      - `UnmappedFeedback`: record for low-confidence or unmapped issues.
      - `FeedbackIssue`: convenience model used by `FeedbackHandler`, keeping `{ presentation_path, criterion, slide_ids, issue: NormalizedIssue }`.

- `slideguard/metrics/yaml_parser.py`
  - `YAMLParser` with responsibilities:
    - Parse existing golden YAML files under `resources/golden/` (legacy structure) into `GoldenYAMLSchema`.
    - Validate structure and criterion names using `Criteria` enum and criteria registry.
    - Provide configurable strictness and logging.

- `slideguard/metrics/eval_pairs.py`
  - `EvalPairsManager` for safe access to `resources/eval_pairs.json` with filtering and atomic writes.

- `slideguard/metrics/evaluation_metrics.py`
  - `EvaluationMetrics` batch engine built on top of `SlideGuardEvaluator`, `YAMLParser`, and the above schemas.

- `slideguard/metrics/feedback_handler.py`
  - `FeedbackHandler` that turns free-form feedback into structured `FeedbackIssue` objects and logs feedback/unmapped cases.

- `slideguard/metrics/observability.py`
  - `metrics_trace` context manager to wrap metrics and feedback operations with Langfuse spans using existing callbacks.

## 3. YAML Parsing and Data Contracts

### 3.1 Golden YAML contract

- **Input (legacy)** under `resources/golden/`:
  - Top-level `evaluation` key with two sections:
    - `deck`: mapping from criterion name (string) to list of strings or objects describing deck-level issues.
    - `slides`: list of entries with at least `slide_id`, `criteria`, and either `comment`, `issue`, or `issues` describing slide-level issues.

- **Normalized representation** (`GoldenYAMLSchema`):
  - `deck[Criteria] = list[NormalizedIssue] `where each legacy string is mapped to `NormalizedIssue(issue=string, severity=1)`.
  - `slides: list[NormalizedSlideEntry]`, where legacy `comment` becomes a single `NormalizedIssue` with `severity=1`.
  - Optional `annotation_status` string preserved if present; otherwise default to fully annotated.

### 3.2 YAMLParser implementation plan

- Implement `YAMLParser` api:
```python
class YAMLParser:
    def __init__(self, criteria_registry, strict_yaml: bool = False, strict_criteria: bool = False, out_of_bounds_action: OutOfBoundsAction = OutOfBoundsAction.SKIP, validation_log_path: Optional[Path] = None):
        ...

    def parse_legacy_yaml(self, yaml_path: Path, slide_count: Optional[int] = None) -> GoldenYAMLSchema:
        ...
```

- Behavior:
  - Read YAML with `yaml.safe_load` and UTF-8 encoding.
  - Validate root structure and `evaluation` key; on invalid structures:
    - Log errors to `resources/yaml_validation_errors.jsonl`.
    - In non-strict mode, return an empty `GoldenYAMLSchema`.
    - In strict mode, raise a `YAMLValidationError`.
  - Map deck criteria names to `Criteria` using `Criteria(name)` with fuzzy fallback (Levenshtein distance) via `python-Levenshtein` when registry confirms the corrected name.
  - For slides, validate `slide_id` and `criteria` presence, handle slide out-of-bounds based on `out_of_bounds_action` (`skip`, `clamp`, or `error`).
  - Normalize issues using `_normalize_issues` to return `list[NormalizedIssue]` from strings, dicts, or lists.
  - Log all validation problems (unknown criteria, invalid entries, empty issue lists) as JSONL lines.

## 4. Eval Pairs Management

- File: `resources/eval_pairs.json` with root `EvalPairsConfig` (see schemas above).
- Implement `EvalPairsManager`:
```python
class EvalPairsManager:
    def __init__(self, pairs_path: Path = Path("resources/eval_pairs.json")):
        ...

    def load_pairs(self, filter_tags: Optional[list[str]] = None, exclude_tags: Optional[list[str]] = None, exclude_disabled: bool = False) -> list[EvalPair]:
        ...

    def save_pairs(self, pairs: list[EvalPair], no_update: bool = False) -> None:
        ...

    def add_pair(self, pair: EvalPair) -> None: ...
    def update_pair(self, index: int, pair: EvalPair) -> None: ...
    def remove_pair(self, index: int) -> None: ...
    def get_all_tags(self) -> list[str]: ...
    def get_pairs_by_tag(self, tag: str) -> list[EvalPair]: ...
```

- Use `filelock.FileLock` on `pairs_path.with_suffix(".lock")` and atomic writes via temp file + `os.replace` to avoid corruption.

## 5. Batch Metrics Engine

### 5.1 EvaluationMetrics API

- File: `slideguard/metrics/evaluation_metrics.py`.
- Constructor:
```python
class EvaluationMetrics:
    def __init__(self, evaluator: SlideGuardEvaluator, yaml_parser: YAMLParser, cache_dir: Path, max_retries: int = 2, max_parallel: int = 3):
        ...
```

- On init, create:
  - `self.metrics_dir = cache_dir / "metrics"`.
  - `self.checkpoints_dir = self.metrics_dir / "checkpoints"`.

- Public methods:
  - `async def evaluate_batch(self, eval_pairs: list[EvalPair], run_id: Optional[str] = None, resume_from: Optional[str] = None, langfuse_client: Optional[Langfuse] = None) -> EvalBatchReport`.
  - `def compute_confusion_matrix(self, predicted: FullEvaluation, ground_truth: GoldenYAMLSchema) -> list[ConfusionEntry]`.
  - `def calculate_metrics(self, entries: list[ConfusionEntry]) -> MetricScores`.

### 5.2 Batch orchestration logic

- `evaluate_batch`:
  - Determine `run_id`:
    - If `resume_from` is provided, use that as `run_id`.
    - Else generate a short UUID.
  - Create `run_dir = self.metrics_dir / run_id`.
  - Load checkpoint from `<checkpoints_dir>/<run_id>.json` if it exists, tracking `completed_indices`.
  - For each `EvalPair` index and value:
    - If index in `completed_indices`, skip reevaluation (or optionally recompute but do not re-add index).
    - Parse golden YAML for the pair: `golden = yaml_parser.parse_legacy_yaml(Path(pair.metric_yaml_path))`.
    - Evaluate presentation via `_evaluate_with_retry(pair, golden, langfuse_client)` under a semaphore (`asyncio.Semaphore(max_parallel)`).
    - Persist per-presentation result:
      - On success, write `<run_dir>/<stem>_evaluation.json` with `FullEvaluation.model_dump_json`.
      - On failure, write `<run_dir>/<stem>_failed.json` with `FailedEvaluation.model_dump_json`.
    - Update `completed_indices` and save checkpoint.
  - After loop, compute confusion entries and metrics for all successful evaluations and assemble `EvalBatchReport`.
  - Save `report.json` in `run_dir`.

### 5.3 Confusion matrix computation using existing result protocols

- Helpers (no `hasattr` or `getattr`):
```python
from slideguard.criteria.types import CriterionResult

def _result_has_issues(result: BaseModel) -> bool:
    if isinstance(result, CriterionResult):
        return len(result.evaluation_results) > 0
    return False

def _result_issue_texts(result: BaseModel) -> list[str]:
    if isinstance(result, CriterionResult):
        return [item.evaluation_element for item in result.evaluation_results]
    return []
```

- Slide-level confusion:
  - Iterate over `FullEvaluation.slide_evaluations`.
  - For each `SlideEvaluationResult` and each non-service criterion in its `evaluations` dict:
    - Skip values that are `NotApplicableResult`.
    - `predicted_positive = _result_has_issues(result)` and result is not `FallbackResult`.
    - `gt_positive = any(entry for entry in ground_truth.slides if entry.slide_id == slide_eval.slide_id and entry.criteria == criterion and entry.issues)`.
    - Create `ConfusionEntry` with predicted/ground truth flags and issue texts.
  - For each `(slide_id, criterion)` in `ground_truth.slides` that has issues but no corresponding prediction:
    - Add an FN entry with `predicted=False`, `ground_truth=True` and empty `predicted_issues`.

- Deck-level confusion:
  - For each criterion in `predicted.deck_evaluations.evaluations`:
    - `predicted_positive` and `gt_positive` defined analogously using `ground_truth.deck`.
  - For deck criteria present in `ground_truth.deck` but not in `predicted.deck_evaluations`, add FN entries.

- Aggregation:
  - `calculate_metrics(entries)` counts TP/FP/FN/TN by `label` and computes precision/recall/F1/accuracy with safe zero-division handling.
  - Build `CriterionMetrics` per `Criteria` using entries filtered by `criterion`.
  - Macro average: arithmetic mean of `precision`, `recall`, `f1`, `accuracy` across criteria that have metrics.
  - Micro average: call `calculate_metrics` on the full `entries` list.

## 6. Feedback → YAML Conversion

### 6.1 FeedbackHandler API

- File: `slideguard/metrics/feedback_handler.py`.
- Constructor:
```python
class FeedbackHandler:
    def __init__(self, llm: ControlledLLM, criteria_registry, feedback_log_dir: Path = Path("resources/feedback_logs"), unmapped_dir: Path = Path("resources/unmapped_feedback"), cache_dir: Optional[Path] = None):
        ...
```

- Public methods:
  - `async def process_presentation_feedback(self, feedback_text: str, presentation_path: str, user_id: Optional[str] = None) -> list[FeedbackIssue]`.

### 6.2 LLM invocation and atomic issues

- Use the underlying chat model from `ControlledLLM` for simple text-to-JSON mapping:
```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda

async def _chunk_feedback(self, feedback_text: str, language: str) -> list[AtomicIssue]:
    criteria_context = self._build_criteria_context()
    prompt = self._build_chunking_prompt(feedback_text, language, criteria_context)
    chain = RunnableLambda(lambda _: prompt) | self.llm.chat_model | StrOutputParser()
    text = await chain.ainvoke({})
    data = json.loads(text)
    return [AtomicIssue(**item) for item in data]
```

- `_build_criteria_context` iterates over `Criteria` (excluding service ones) and uses `criteria_registry` to include descriptions in the prompt.
- `_build_chunking_prompt` instructs the model to:
  - Split feedback into atomic issues.
  - Map each issue to a `criterion` (by enum value) and list of `slide_ids`.
  - Provide `issue_text`, `confidence`, and `needs_review`.

### 6.3 Feedback processing and logging

- `process_presentation_feedback` steps:
  - Compute `feedback_hash` over `{feedback_text, presentation_path}` and check recent JSONL logs for duplicates within a time window.
  - Detect language using a simple Cyrillic vs Latin heuristic.
  - Call `_chunk_feedback` and iterate over `AtomicIssue` results:
    - Skip service criteria.
    - For low-confidence or `needs_review` entries, log `UnmappedFeedback` JSON files under `resources/unmapped_feedback` and skip these for now.
    - For high-confidence entries, create `FeedbackIssue` objects with `criterion`, `slide_ids`, and a `NormalizedIssue` with `severity` defaulting to 2.
  - Append a `FeedbackEntry` JSONL line under `resources/feedback_logs/feedback_<date>.jsonl` with original text, hash, and normalized issues.
  - Return the list of `FeedbackIssue` objects to the caller.

- These `FeedbackIssue` objects can later be used to:
  - Update or generate YAML files (via `YAMLParser` and `GoldenYAMLSchema`).
  - Enrich `EvalPair` definitions or produce new pairs.

## 7. Langfuse Observability for Metrics and Feedback

- File: `slideguard/metrics/observability.py`.
- Implement `metrics_trace` using existing Langfuse utilities and callbacks:
```python
from contextlib import contextmanager
from slideguard.crew.callbacks import ImageStrippingLangfuseHandler

@contextmanager
def metrics_trace(run_id: str, operation: str, metadata: Optional[dict[str, Any]] = None, langfuse_client: Optional[Langfuse] = None):
    if not langfuse_client:
        yield None
        return
    handler = ImageStrippingLangfuseHandler()
    try:
        yield handler
    finally:
        try:
            langfuse_client.flush()
        except Exception:
            logger.warning("Failed to flush Langfuse client")
```

- Use `metrics_trace` in `EvaluationMetrics.evaluate_batch` and in `FeedbackHandler.process_presentation_feedback`:
  - Wrap the batch run as a high-level span with metadata (`total_pairs`, `tags`, etc.).
  - For feedback, record the presentation and maybe a hash of the feedback text but not the full text if privacy requires.

## 8. CLI Integration in `slideguard/main.py`

### 8.1 Metrics Typer sub-app

- Add imports near the top:
```python
from slideguard.metrics.eval_pairs import EvalPairsManager
from slideguard.metrics.yaml_parser import YAMLParser, OutOfBoundsAction
from slideguard.metrics.evaluation_metrics import EvaluationMetrics
from slideguard.metrics.feedback_handler import FeedbackHandler
```

- Define and attach `metrics_app`:
```python
metrics_app = typer.Typer(help="Evaluation metrics and feedback management")
app.add_typer(metrics_app, name="metrics")
```


### 8.2 `metrics batch` command

- Implement `metrics batch` with options:
  - `--pairs / -p`: path to `eval_pairs.json`.
  - `--output / -o`: output directory (default within cache dir, but still printed).
  - `--preset`: reserved for future weighting.
  - `--resume`: run ID to resume.
  - `--strict-yaml`, `--strict-criteria`, `--out-of-bounds-action`.
  - `--filter-tag`, `--exclude-tag`, `--exclude-disabled`.
  - `--use-langfuse`, `--max-parallel`.

- Steps inside command:
  - Load `SlideGuardConfig` and Langfuse client using existing helpers.
  - Create LLM via `create_llm_from_config`; exit with configuration help if not configured.
  - Build criteria registry provider and registry.
  - Construct `SlideGuardEvaluator` exactly as in `eval run`, reusing `FileManager` and `CacheManager` with config paths.
  - Instantiate `YAMLParser` with registry and CLI flags.
  - Instantiate `EvaluationMetrics` with evaluator, parser, and `Path(config.cache_dir)`.
  - Load pairs from `EvalPairsManager` with filters.
  - Run `asyncio.run(metrics_engine.evaluate_batch(...))`.
  - Print a concise summary and the `report.json` path under the metrics directory.

### 8.3 `metrics feedback` command

- Options:
  - `--text / -t`: feedback text.
  - `--presentation / -p`: presentation path.
  - `--user-id`: optional.
  - `--dry-run`: skip writing logs if set.

- Inside command:
  - Load config and LLM; build registry.
  - Instantiate `FeedbackHandler` with LLM and registry.
  - Run `asyncio.run(handler.process_presentation_feedback(...))`.
  - If not `dry_run`, ensure logs are written.
  - Print the list of resulting `FeedbackIssue` entries (criterion, slide_ids, issue text, severity).

### 8.4 `metrics list-tags` and `metrics validate-yaml`

- `metrics list-tags`:
  - Use `EvalPairsManager` to collect and print sorted tags.

- `metrics validate-yaml`:
  - Use `YAMLParser` to parse a given YAML path, printing deck criteria and slide entry counts or an error with non-zero exit code.

## 9. Future UI Integration Hooks (Planning Only)

- Add minimal, non-invasive hooks in `slideguard/ui/app.py` for future phases:
  - A method on `SlideGuardUI` to submit general presentation feedback (text area) and send it to CLI-equivalent `FeedbackHandler` logic via an internal helper or background task.
  - Keep feedback submission decoupled for now: store feedback via the same JSONL/unmapped pipeline as CLI.
  - In a later phase, create a background job or CLI command that:
    - Reads `feedback_logs` and `unmapped_feedback`.
    - Suggests new or updated `EvalPair` entries based on recurring feedback patterns.

- No UI behavior change is required in the current phase; only plan the interfaces so that feedback collected from UI can later be converted into YAML and new `EvalPair` configurations.

## 10. Implementation Checklist

- **Step 1**: Create `slideguard/metrics/` package and implement `schemas.py` with YAML, eval pair, confusion, metrics, checkpoint, and feedback models.
- **Step 2**: Implement `yaml_parser.py` with legacy-to-normalized conversion, strict/permissive modes, fuzzy criteria matching, and JSONL logging; add `YAMLValidationError` exception.
- **Step 3**: Implement `eval_pairs.py` with `EvalPairsManager` using file locks and atomic writes for `resources/eval_pairs.json`.
- **Step 4**: Implement `evaluation_metrics.py` with batch orchestration, retry and checkpoint handling, confusion matrix logic using `CriterionResult` protocols, and metric aggregation.
- **Step 5**: Implement `feedback_handler.py` using `ControlledLLM.chat_model` for JSON chunking, duplicate detection, unmapped logging, and returning structured `FeedbackIssue` objects.
- **Step 6**: Implement `observability.py` with `metrics_trace` and integrate it into `EvaluationMetrics.evaluate_batch` and `FeedbackHandler.process_presentation_feedback`.
- **Step 7**: Extend `slideguard/main.py` with the `metrics` Typer sub-app and the four commands, reusing existing evaluator/config wiring.
- **Step 8**: Add required dependencies (`python-Levenshtein`, `filelock`) to `pyproject.toml`, create an example `resources/eval_pairs.json`, and run end-to-end smoke tests for metrics and feedback workflows.