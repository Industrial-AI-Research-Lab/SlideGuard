# Metrics Module Overview

This document summarizes the current functionality in `slideguard/metrics`, the main use cases it supports, and the key classes/methods with their inputs, internal logic, and outputs.

## Intended Use Cases
- **Collect and normalize free-form user feedback** about a presentation into structured `FeedbackIssue` items aligned to known criteria, with language-aware extraction and confidence filtering.
- **Evaluate model-generated presentation assessments** against golden annotations, producing confusion matrices and aggregated metrics.
- **Manage evaluation pairs configuration** (presentation path + golden YAML) for batch runs.
- **Parse and validate golden YAML files** into normalized structures for metrics.
- **Emit observability traces** for feedback processing and batch metrics via Langfuse.

## Components

### FeedbackHandler (`feedback_handler.py`)
**Purpose:** Turn a free-text feedback message into normalized, criterion-linked issues with logging of low-confidence items.

- **Constructor**
  - Inputs: `llm: ControlledLLM`, `criteria_registry: CriteriaRegistry`, optional dirs and `min_confidence`.
  - Sets up directories and compiles a LangGraph state machine.

- **`process_presentation_feedback(feedback_text, presentation_path, user_id=None, persist=True, langfuse_client=None) -> list[FeedbackIssue]`**
  - Logic: deduplicate via SHA256 hash; run graph; optionally log results and low-confidence items; returns normalized issues.
  - Output: list of `FeedbackIssue` (criterion + slide ids + normalized issue).

- **Graph nodes**
  - `detect_language`: uses `_detect_language_robust` (LLM with structured output; fallback heuristic) to set `language`.
  - `chunk_feedback`: builds criteria context and prompt; calls `ControlledLLM.with_structured_output_retry` with `AtomicIssuesList`; returns `atoms`.
  - `normalize`: filters service criteria; drops low-confidence or needs_review below threshold; builds `FeedbackIssue`; collects low-confidence `AtomicIssue`.
  - `finalize`: when `persist` is True, appends JSONL feedback logs; writes unmapped/low-confidence items to a separate file.

- **Helper behaviors**
  - `_build_prompt`: system/user messages instruct atomic extraction, criterion mapping, slide ids (0-indexed), confidence, and needs_review; enforces output language based on detection.
  - `_build_criteria_context`: lists slide/deck criteria descriptions from the registry.
  - `_detect_language_robust`: LLM-based detection (`LanguageDetectionResult`); falls back to Cyrillic check.
  - Duplicate detection: scans current log file for matching `feedback_hash`.
  - Persistence: writes `FeedbackEntry` or `UnmappedFeedback` JSONL with UTC dates.

### EvaluationMetrics (`evaluation_metrics.py`)
**Purpose:** Run batch evaluations, compare predictions to ground truth, and compute metrics with semantic issue matching.

- **Constructor**
  - Inputs: `evaluator: SlideGuardEvaluator`, `cache_dir`, `yaml_loader` (default `load_normalized_yaml`), `max_retries`, `max_parallel`, optional `llm` for semantic matching.
  - Sets up metrics directory, semaphore, SQLite checkpointer, and compiles graph.

- **`evaluate_batch(eval_pairs, run_id=None, resume_from=None, langfuse_client=None) -> EvalBatchReport`**
  - Logic: build list of per-pair states; run `self._graph.abatch` with `max_concurrency`; persist success/failure JSON; compute confusion entries; aggregate per-criterion, macro, micro metrics; write `report.json`.
  - Output: `EvalBatchReport` with counts, failures, per-criterion metrics, macro/micro scores.

- **Graph nodes (per pair)**
  - `load_golden`: loads YAML via `yaml_loader`; on `YAMLFormatError` emits `failure`.
  - `run_evaluator`: if golden loaded, calls `_evaluate_pair` with retries and optional semaphore; returns `evaluation` or `failure`.

- **Semantic matching**
  - `_match_issues_semantically(predicted_issue, gt_issue)`: uses LLM+`IssueMatchResult` (confidence >= 0.7) to decide match; fallback exact match without LLM or on error.
  - `_match_issue_lists(predicted_issues, gt_issues)`: pairwise matching to allow wording differences.

- **Confusion matrix**
  - `compute_confusion_matrix(predicted: FullEvaluation, ground_truth: GoldenYAMLSchema) -> list[ConfusionEntry]` (async):
    - Slide-level: for each non-service criterion result, compare predicted vs ground truth issues with semantic matching; label TP/FP/FN/TN.
    - Deck-level: same logic for deck criteria.
    - Adds FN entries for missing predictions.

- **Metrics aggregation**
  - `calculate_metrics(entries) -> MetricScores`: precision/recall/F1/accuracy with safe zero handling.
  - `_build_per_criterion_metrics(entries) -> (list[CriterionMetrics], MetricScores)`: per-criterion buckets and macro average.
  - `_compute_macro_average`: mean of per-criterion metrics.

- **Helpers**
  - `_build_slide_criteria`, `_build_deck_criteria`: derive criteria sets from golden YAML.
  - `_result_issue_texts`, `_result_has_issues`, `_label`: utility for confusion entries.
  - Persistence: `_persist_success/_persist_failure` JSON outputs per pair; `_write_report`.

### Schemas (`schemas.py`)
Core Pydantic models:
- Feedback: `AtomicIssue`, `FeedbackIssue`, `FeedbackEntry`, `UnmappedFeedback`.
- Golden data: `NormalizedIssue`, `NormalizedSlideEntry`, `NormalizedDeckEntry`, `GoldenYAMLSchema`.
- Batch config: `EvalPair`, `EvalPairsConfig`.
- Metrics: `ConfusionEntry`, `MetricScores`, `CriterionMetrics`, `EvalBatchReport`.

### YAML Loader (`yaml_loader.py`)
- `load_normalized_yaml(path) -> GoldenYAMLSchema`
  - Reads YAML, validates structure, parses deck and slide sections.
  - Coerces criteria to `Criteria` enums; validates deck vs slide level.
  - Normalizes issues (strings or dicts) into `NormalizedIssue`; enforces non-empty text; type-coerces severity.
  - Raises `YAMLFormatError` on invalid content.

### Eval Pairs Manager (`eval_pairs.py`)
- Manages `resources/eval_pairs.json` with file locking and atomic writes.
- `load_pairs(filter_tags=None, exclude_tags=None, exclude_disabled=False) -> list[EvalPair]`.
- CRUD helpers: `add_pair`, `update_pair`, `remove_pair`, `save_pairs`.
- Tag utilities: `get_all_tags`, `get_pairs_by_tag`.

### Observability (`observability.py`)
- `metrics_trace(run_id, operation, metadata=None, langfuse_client=None)` context manager:
  - Starts Langfuse trace, attaches metadata, ends/flushes on exit; logs warnings on failures.

## Inputs and Outputs at a Glance
- **Feedback ingestion:** raw feedback text + presentation path → `FeedbackIssue` list (normalized, criterion-linked); logs JSONL for audit and low-confidence.
- **Batch evaluation:** list of `EvalPair` (presentation path + golden YAML) → `EvalBatchReport` + per-pair JSON outputs (success/failure) and confusion entries derived via semantic matching.
- **Golden YAML:** YAML deck/slides definition → `GoldenYAMLSchema` Pydantic model or `YAMLFormatError`.
- **Eval pairs config:** JSON file → filtered list of `EvalPair`; supports tag-based selection and edits.

## How to Use (common flows)
- **Process user feedback**
  - Instantiate `FeedbackHandler(llm, criteria_registry)`; call `process_presentation_feedback(feedback_text, presentation_path, user_id, persist, langfuse_client)`.

- **Run metrics batch**
  - Prepare `EvalPair` list (or use `EvalPairsManager` to load from `resources/eval_pairs.json`).
  - Instantiate `EvaluationMetrics(evaluator, cache_dir, max_parallel, llm=controlled_llm_for_matching)`.
  - Await `evaluate_batch(eval_pairs, run_id, resume_from, langfuse_client)`; inspect `report.json` and per-pair JSON outputs.

- **Load golden annotations**
  - Call `load_normalized_yaml(Path(metric_yaml_path))` to validate and get `GoldenYAMLSchema`.

- **Manage eval pairs**
  - Use `EvalPairsManager` methods to list/filter/add/update/remove pairs with locking and atomic writes.


