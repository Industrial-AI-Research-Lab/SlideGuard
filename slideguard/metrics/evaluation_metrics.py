from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from langchain_core.prompts import ChatPromptTemplate
from langfuse import Langfuse
from langgraph.checkpoint import SqliteSaver
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from slideguard.criteria.types import CriterionResult
from slideguard.crew.controlled_llm import ControlledLLM
from slideguard.crew.evaluator import (
    FallbackResult,
    NotApplicableResult,
    SlideGuardEvaluator,
)
from slideguard.metrics.observability import metrics_trace
from slideguard.metrics.schemas import (
    ConfusionEntry,
    EvalBatchReport,
    EvalPair,
    FailedEvaluation,
    GoldenYAMLSchema,
    MetricScores,
    CriterionMetrics,
)
from slideguard.metrics.yaml_loader import load_normalized_yaml, YAMLFormatError
from slideguard.schemes import Criteria, FullEvaluation


logger = logging.getLogger(__name__)


class IssueMatchResult(BaseModel):
    matches: bool = Field(description="Whether the two issues match semantically")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in the match (0.0-1.0)")
    reason: Optional[str] = Field(None, description="Brief explanation of why they match or don't match")


class EvaluationSuccess(BaseModel):
    pair: EvalPair
    golden: GoldenYAMLSchema
    evaluation: FullEvaluation


class MetricsGraphState(BaseModel):
    run_id: str
    pair: EvalPair
    golden: Optional[GoldenYAMLSchema] = None
    evaluation: Optional[FullEvaluation] = None
    failure: Optional[FailedEvaluation] = None


class EvaluationMetrics:
    def __init__(
        self,
        evaluator: SlideGuardEvaluator,
        cache_dir: Path,
        yaml_loader=load_normalized_yaml,
        max_retries: int = 2,
        max_parallel: Optional[int] = 3,
        llm: Optional[ControlledLLM] = None,
    ) -> None:
        self.evaluator = evaluator
        self.yaml_loader = yaml_loader
        self.cache_dir = cache_dir
        self.max_retries = max_retries
        self.max_parallel = max_parallel
        self.llm = llm
        self.metrics_dir = (self.cache_dir / "metrics").resolve()
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self._semaphore = asyncio.Semaphore(self.max_parallel) if self.max_parallel else None
        self._checkpointer = SqliteSaver(str(self.metrics_dir / "metrics_state.sqlite"))
        self._graph = self._build_graph()
        self._active_langfuse_client: Optional[Langfuse] = None
        self._active_run_dir: Optional[Path] = None
        self._match_semaphore = asyncio.Semaphore(self.max_parallel or 5)

    async def evaluate_batch(
        self,
        eval_pairs: Sequence[EvalPair],
        run_id: Optional[str] = None,
        resume_from: Optional[str] = None,
        langfuse_client: Optional[Langfuse] = None,
    ) -> EvalBatchReport:
        run_key = resume_from or run_id or uuid.uuid4().hex[:8]
        metadata = {"total_pairs": len(eval_pairs)}
        run_dir = self.metrics_dir / run_key
        run_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = self._load_checkpoint(run_dir)
        completed_indices = set(checkpoint.get("completed_indices", []))
        failed_indices = set(checkpoint.get("failed_indices", []))
        yaml_failures: set[str] = set(checkpoint.get("yaml_failures", []))
        
        with metrics_trace(run_key, "metrics_batch", metadata, langfuse_client) as trace:
            self._active_langfuse_client = langfuse_client
            self._active_run_dir = run_dir

            restored_successes, restored_failures = self._load_completed_results(run_dir, eval_pairs, completed_indices, failed_indices)
            successes: List[EvaluationSuccess] = list(restored_successes)
            failures: List[FailedEvaluation] = list(restored_failures)

            pairs_to_run: List[Tuple[int, EvalPair]] = [(idx, pair) for idx, pair in enumerate(eval_pairs) if idx not in completed_indices and idx not in failed_indices]

            list_of_inputs = []
            for pair_index, pair in pairs_to_run:
                initial_state = MetricsGraphState(
                    run_id=run_key,
                    pair=pair,
                )
                list_of_inputs.append(initial_state)
            
            if list_of_inputs:
                batch_config = {
                    "configurable": {"thread_id": run_key},
                    "max_concurrency": self.max_parallel if self.max_parallel else 5,
                }
                
                result_states = await self._graph.abatch(list_of_inputs, config=batch_config)
            else:
                result_states = []
            
            for (pair_index, pair), result_state in zip(pairs_to_run, result_states):
                if result_state.evaluation and result_state.golden:
                    success = EvaluationSuccess(pair=pair, golden=result_state.golden, evaluation=result_state.evaluation)
                    successes.append(success)
                    completed_indices.add(pair_index)
                    self._persist_success(pair_index, pair, result_state.evaluation)
                elif result_state.failure:
                    failures.append(result_state.failure)
                    failed_indices.add(pair_index)
                    if result_state.failure.error_type == "YAMLFormatError":
                        yaml_failures.add(pair.metric_yaml_path)
                    self._persist_failure(pair_index, pair, result_state.failure)
            self._save_checkpoint(run_dir, completed_indices, failed_indices, yaml_failures)

            self._active_langfuse_client = None
            self._active_run_dir = None
            
            confusion_entries: List[ConfusionEntry] = []
            for success in successes:
                entries = await self.compute_confusion_matrix(success.evaluation, success.golden)
                confusion_entries.extend(entries)
            
            per_criterion_metrics, macro_metrics = self._build_per_criterion_metrics(confusion_entries)
            micro_metrics = self.calculate_metrics(confusion_entries)
            report = EvalBatchReport(
                run_id=run_key,
                total_presentations=len(eval_pairs),
                successful=len(successes),
                failed=len(failures),
                failed_presentations=failures,
                yaml_failures=sorted(yaml_failures),
                per_criterion_metrics=per_criterion_metrics,
                macro_avg_metrics=macro_metrics,
                micro_avg_metrics=micro_metrics,
            )
            self._write_report(run_dir, report)
            self._write_summary(run_dir, report)
            if trace:
                try:
                    trace.update(
                        output={
                            "successful": len(successes),
                            "failed": len(failures),
                            "run_dir": str(run_dir),
                        }
                    )
                except Exception as exc:
                    logger.warning("Failed to update Langfuse trace: %s", exc, exc_info=True)
            return report

    def _build_graph(self):
        graph = StateGraph(MetricsGraphState)
        graph.add_node("load_golden", self._node_load_golden)
        graph.add_node("run_evaluator", self._node_run_evaluator)
        graph.add_edge("load_golden", "run_evaluator")
        graph.add_edge("run_evaluator", END)
        graph.set_entry_point("load_golden")
        return graph.compile(checkpointer=self._checkpointer)

    def _node_load_golden(self, state: MetricsGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
        try:
            golden = self.yaml_loader(Path(state.pair.metric_yaml_path))
            return {"golden": golden}
        except YAMLFormatError as exc:
            failure = FailedEvaluation(
                presentation_path=state.pair.presentation_path,
                error_type="YAMLFormatError",
                error_message=str(exc),
                traceback=None,
                retry_count=0,
            )
            return {"failure": failure, "golden": None}

    async def _node_run_evaluator(self, state: MetricsGraphState, config: Dict[str, Any]) -> Dict[str, Any]:
        if state.failure or not state.golden:
            return {}
        
        pair_index = 0
        evaluation, failure = await self._evaluate_pair(state.pair, state.golden, pair_index, self._active_langfuse_client)
        if evaluation:
            return {"evaluation": evaluation, "failure": None}
        if failure:
            return {"failure": failure, "evaluation": None}
        return {}

    async def _evaluate_pair(
        self,
        pair: EvalPair,
        golden: GoldenYAMLSchema,
        pair_index: int,
        langfuse_client: Optional[Langfuse],
    ) -> Tuple[Optional[FullEvaluation], Optional[FailedEvaluation]]:
        slide_criteria = self._build_slide_criteria(golden, bool(golden.deck))
        deck_criteria = self._build_deck_criteria(golden)
        attempts = 0
        delay = 1
        while attempts <= self.max_retries:
            try:
                if self._semaphore:
                    async with self._semaphore:
                        evaluation = await self.evaluator.evaluate_presentation(
                            presentation_path=pair.presentation_path,
                            slide_criterias=slide_criteria,
                            deck_criterias=deck_criteria,
                            langfuse_client=langfuse_client,
                        )
                else:
                    evaluation = await self.evaluator.evaluate_presentation(
                        presentation_path=pair.presentation_path,
                        slide_criterias=slide_criteria,
                        deck_criterias=deck_criteria,
                        langfuse_client=langfuse_client,
                    )
                return evaluation, None
            except Exception as exc:
                attempts += 1
                logger.error("Evaluation failed for %s attempt %s", pair.presentation_path, attempts, exc_info=True)
                if attempts > self.max_retries:
                    failure = FailedEvaluation(
                        presentation_path=pair.presentation_path,
                        error_type=exc.__class__.__name__,
                        error_message=str(exc),
                        traceback=traceback.format_exc(),
                        retry_count=attempts - 1,
                    )
                    return None, failure
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
        return None, None

    async def _match_issues_semantically(self, predicted_issue: str, gt_issue: str) -> bool:
        if not self.llm:
            return predicted_issue.lower().strip() == gt_issue.lower().strip()
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert at determining if two presentation feedback issues are semantically equivalent, even if worded differently. Consider that they may express the same concern in different ways."),
            ("user", f"""Determine if these two issues are semantically equivalent (express the same concern):

Predicted issue: "{predicted_issue}"
Ground truth issue: "{gt_issue}"

Consider:
- They match if they express the same core problem or suggestion
- Different wording but same meaning = match
- Different concerns even if similar wording = no match
- Examples:
  - "add experimental results" matches "add a slide for results of the experiments"
  - "add experimental results" does NOT match "slide results should come at the end, not at the beginning"
"""),
        ])
        
        chain = prompt | self.llm.with_structured_output_retry(IssueMatchResult)
        try:
            async with self._match_semaphore:
                result = await chain.ainvoke({})
            if result.pydantic:
                return result.pydantic.matches and result.pydantic.confidence >= 0.7
        except Exception as exc:
            logger.warning(f"Semantic matching failed, falling back to exact match: {exc}")
        
        return predicted_issue.lower().strip() == gt_issue.lower().strip()

    def _tokenize(self, text: str) -> List[str]:
        return [t for t in "".join([c if c.isalnum() else " " for c in text.lower()]).split() if t]

    def _build_bm25_index(self, docs: List[str]):
        tokenized = [self._tokenize(doc) for doc in docs]
        df: Dict[str, int] = {}
        for doc_tokens in tokenized:
            for term in set(doc_tokens):
                df[term] = df.get(term, 0) + 1
        n = len(tokenized) or 1
        idf = {term: max(0.0, (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}
        avgdl = sum(len(t) for t in tokenized) / n
        return tokenized, idf, avgdl

    def _bm25_scores(self, query_tokens: List[str], docs_tokens: List[List[str]], idf: Dict[str, float], avgdl: float) -> List[float]:
        scores: List[float] = []
        k1 = 1.5
        b = 0.75
        for doc_tokens in docs_tokens:
            score = 0.0
            doc_len = len(doc_tokens) or 1
            tf: Dict[str, int] = {}
            for term in doc_tokens:
                tf[term] = tf.get(term, 0) + 1
            for term in query_tokens:
                if term not in tf:
                    continue
                term_idf = idf.get(term, 0.0)
                freq = tf[term]
                denom = freq + k1 * (1 - b + b * doc_len / max(avgdl, 1e-6))
                score += term_idf * freq * (k1 + 1) / denom
            scores.append(score)
        return scores

    async def _match_issue_sets(self, predicted: List[str], ground_truth: List[str], top_n: int = 3) -> Tuple[List[Tuple[int, int, float]], List[int], List[int]]:
        if not predicted and not ground_truth:
            return [], [], []
        if not ground_truth:
            return [], list(range(len(predicted))), []
        if not predicted:
            return [], [], list(range(len(ground_truth)))

        docs_tokens, idf, avgdl = self._build_bm25_index(ground_truth)
        candidates: List[Tuple[int, int, float]] = []
        for p_idx, issue in enumerate(predicted):
            q_tokens = self._tokenize(issue)
            if not q_tokens:
                continue
            scores = self._bm25_scores(q_tokens, docs_tokens, idf, avgdl)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            for g_idx, score in ranked[: min(top_n, len(ranked))]:
                candidates.append((p_idx, g_idx, score))

        if self.llm and candidates:
            tasks = []
            for p_idx, g_idx, score in candidates:
                tasks.append(self._match_candidate(predicted[p_idx], ground_truth[g_idx], p_idx, g_idx, score))
            results = await asyncio.gather(*tasks)
            candidates = results

        norm_candidates: List[Tuple[int, int, float]] = []
        for p_idx, g_idx, score in candidates:
            norm = score / (score + 1.0) if score > 0 else 0.0
            norm_candidates.append((p_idx, g_idx, norm))

        norm_candidates = sorted(norm_candidates, key=lambda x: x[2], reverse=True)
        matched_pred: set[int] = set()
        matched_gt: set[int] = set()
        matches: List[Tuple[int, int, float]] = []
        threshold = 0.55 if self.llm else 0.35
        for p_idx, g_idx, conf in norm_candidates:
            if conf < threshold:
                continue
            if p_idx in matched_pred or g_idx in matched_gt:
                continue
            matched_pred.add(p_idx)
            matched_gt.add(g_idx)
            matches.append((p_idx, g_idx, conf))

        unmatched_pred = [i for i in range(len(predicted)) if i not in matched_pred]
        unmatched_gt = [i for i in range(len(ground_truth)) if i not in matched_gt]
        return matches, unmatched_pred, unmatched_gt

    async def _match_candidate(self, pred_text: str, gt_text: str, p_idx: int, g_idx: int, fallback_score: float) -> Tuple[int, int, float]:
        try:
            is_match = await self._match_issues_semantically(pred_text, gt_text)
            if not is_match:
                return p_idx, g_idx, 0.0
            return p_idx, g_idx, 1.0
        except Exception:
            return p_idx, g_idx, fallback_score

    async def compute_confusion_matrix(self, predicted: FullEvaluation, ground_truth: GoldenYAMLSchema) -> List[ConfusionEntry]:
        entries: List[ConfusionEntry] = []
        slide_gt: Dict[Tuple[int, Criteria], List[str]] = {}
        for entry in ground_truth.slides:
            if not entry.issues:
                continue
            key = (entry.slide_id, entry.criteria)
            slide_gt[key] = [issue.issue for issue in entry.issues]

        seen_slide_keys: set[Tuple[int, Criteria]] = set()
        for slide_eval in predicted.slide_evaluations or []:
            for criteria, value in (slide_eval.evaluations or {}).items():
                if criteria.is_service_criteria():
                    continue
                if isinstance(value, NotApplicableResult):
                    continue
                predicted_issues_list = self._result_issue_texts(value)
                gt_issues_list = slide_gt.get((slide_eval.slide_id, criteria), [])
                matches, unmatched_pred, unmatched_gt = await self._match_issue_sets(predicted_issues_list, gt_issues_list)
                for p_idx, g_idx, _conf in matches:
                    entries.append(
                        ConfusionEntry(
                            presentation_path=predicted.slide_deck_path,
                            slide_id=slide_eval.slide_id,
                            criterion=criteria,
                            predicted=True,
                            ground_truth=True,
                            label="TP",
                            predicted_issues=[predicted_issues_list[p_idx]],
                            ground_truth_issues=[gt_issues_list[g_idx]],
                            reason=None,
                        )
                    )
                for p_idx in unmatched_pred:
                    entries.append(
                        ConfusionEntry(
                            presentation_path=predicted.slide_deck_path,
                            slide_id=slide_eval.slide_id,
                            criterion=criteria,
                            predicted=True,
                            ground_truth=False,
                            label="FP",
                            predicted_issues=[predicted_issues_list[p_idx]],
                            ground_truth_issues=[],
                            reason="unmatched_prediction",
                        )
                    )
                for g_idx in unmatched_gt:
                    entries.append(
                        ConfusionEntry(
                            presentation_path=predicted.slide_deck_path,
                            slide_id=slide_eval.slide_id,
                            criterion=criteria,
                            predicted=False,
                            ground_truth=True,
                            label="FN",
                            predicted_issues=[],
                            ground_truth_issues=[gt_issues_list[g_idx]],
                            reason="missing_prediction",
                        )
                    )
                seen_slide_keys.add((slide_eval.slide_id, criteria))

        for key, issues in slide_gt.items():
            if key in seen_slide_keys:
                continue
            for issue in issues:
                entries.append(
                    ConfusionEntry(
                        presentation_path=predicted.slide_deck_path,
                        slide_id=key[0],
                        criterion=key[1],
                        predicted=False,
                        ground_truth=True,
                        label="FN",
                        predicted_issues=[],
                        ground_truth_issues=[issue],
                        reason="missing_prediction",
                    )
                )

        deck_gt = {criterion: [issue.issue for issue in issues] for criterion, issues in ground_truth.deck.items() if issues}
        predicted_deck = (predicted.deck_evaluations.evaluations if predicted.deck_evaluations else {}) or {}

        seen_deck: set[Criteria] = set()
        for criterion, value in predicted_deck.items():
            predicted_issues_list = self._result_issue_texts(value)
            gt_issues_list = deck_gt.get(criterion, [])
            matches, unmatched_pred, unmatched_gt = await self._match_issue_sets(predicted_issues_list, gt_issues_list)
            for p_idx, g_idx, _conf in matches:
                entries.append(
                    ConfusionEntry(
                        presentation_path=predicted.slide_deck_path,
                        slide_id=None,
                        criterion=criterion,
                        predicted=True,
                        ground_truth=True,
                        label="TP",
                        predicted_issues=[predicted_issues_list[p_idx]],
                        ground_truth_issues=[gt_issues_list[g_idx]],
                        reason=None,
                    )
                )
            for p_idx in unmatched_pred:
                entries.append(
                    ConfusionEntry(
                        presentation_path=predicted.slide_deck_path,
                        slide_id=None,
                        criterion=criterion,
                        predicted=True,
                        ground_truth=False,
                        label="FP",
                        predicted_issues=[predicted_issues_list[p_idx]],
                        ground_truth_issues=[],
                        reason="unmatched_prediction",
                    )
                )
            for g_idx in unmatched_gt:
                entries.append(
                    ConfusionEntry(
                        presentation_path=predicted.slide_deck_path,
                        slide_id=None,
                        criterion=criterion,
                        predicted=False,
                        ground_truth=True,
                        label="FN",
                        predicted_issues=[],
                        ground_truth_issues=[gt_issues_list[g_idx]],
                        reason="missing_prediction",
                    )
                )
            seen_deck.add(criterion)

        for criterion, issues in deck_gt.items():
            if criterion in seen_deck:
                continue
            for issue in issues:
                entries.append(
                    ConfusionEntry(
                        presentation_path=predicted.slide_deck_path,
                        slide_id=None,
                        criterion=criterion,
                        predicted=False,
                        ground_truth=True,
                        label="FN",
                        predicted_issues=[],
                        ground_truth_issues=[issue],
                        reason="missing_prediction",
                    )
                )
        return entries

    def calculate_metrics(self, entries: Sequence[ConfusionEntry]) -> MetricScores:
        tp = sum(1 for e in entries if e.label == "TP")
        fp = sum(1 for e in entries if e.label == "FP")
        fn = sum(1 for e in entries if e.label == "FN")
        tn = sum(1 for e in entries if e.label == "TN")
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        if precision + recall:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = 0.0
        accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) else 0.0
        return MetricScores(tp=tp, fp=fp, fn=fn, tn=tn, precision=precision, recall=recall, f1=f1, accuracy=accuracy)

    def _build_per_criterion_metrics(self, entries: Sequence[ConfusionEntry]) -> Tuple[List[CriterionMetrics], MetricScores]:
        buckets: Dict[Criteria, List[ConfusionEntry]] = {}
        for entry in entries:
            buckets.setdefault(entry.criterion, []).append(entry)
        criterion_metrics: List[CriterionMetrics] = []
        for criterion, bucket in sorted(buckets.items(), key=lambda item: item[0].value):
            metrics = self.calculate_metrics(bucket)
            criterion_metrics.append(
                CriterionMetrics(
                    criterion=criterion,
                    slide_metrics=metrics if criterion.is_slide_criteria() else None,
                    deck_metrics=metrics if criterion.is_deck_criteria() else None,
                )
            )
        if criterion_metrics:
            macro_metrics = self._compute_macro_average([cm.slide_metrics or cm.deck_metrics for cm in criterion_metrics if (cm.slide_metrics or cm.deck_metrics)])
        else:
            macro_metrics = MetricScores()
        return criterion_metrics, macro_metrics

    def _compute_macro_average(self, metrics: Sequence[MetricScores]) -> MetricScores:
        if not metrics:
            return MetricScores()
        count = len(metrics)
        tp = sum(m.tp for m in metrics)
        fp = sum(m.fp for m in metrics)
        fn = sum(m.fn for m in metrics)
        tn = sum(m.tn for m in metrics)
        precision = sum(m.precision for m in metrics) / count
        recall = sum(m.recall for m in metrics) / count
        f1 = sum(m.f1 for m in metrics) / count
        accuracy = sum(m.accuracy for m in metrics) / count
        return MetricScores(tp=tp, fp=fp, fn=fn, tn=tn, precision=precision, recall=recall, f1=f1, accuracy=accuracy)

    def _result_has_issues(self, value: BaseModel) -> bool:
        if isinstance(value, FallbackResult):
            return False
        if isinstance(value, CriterionResult):
            return bool(value.evaluation_results)
        return True

    def _result_issue_texts(self, value: BaseModel) -> List[str]:
        if isinstance(value, CriterionResult):
            return [item.evaluation_element for item in value.evaluation_results]
        return []

    def _label(self, predicted_positive: bool, ground_truth_positive: bool) -> str:
        if predicted_positive and ground_truth_positive:
            return "TP"
        if predicted_positive and not ground_truth_positive:
            return "FP"
        if ground_truth_positive:
            return "FN"
        return "TN"

    def _build_slide_criteria(self, golden: GoldenYAMLSchema, include_deck_requirements: bool) -> List[Criteria]:
        slide_set = {entry.criteria for entry in golden.slides}
        slide_set.discard(Criteria.slide_type)
        slide_set.discard(Criteria.slide_description)
        if include_deck_requirements:
            slide_set.update({Criteria.slide_type, Criteria.slide_description})
        elif slide_set:
            slide_set.add(Criteria.slide_type)
        return sorted(slide_set, key=lambda c: c.value)

    def _build_deck_criteria(self, golden: GoldenYAMLSchema) -> List[Criteria]:
        deck_set = {criterion for criterion in golden.deck.keys() if criterion.is_deck_criteria()}
        return sorted(deck_set, key=lambda c: c.value)

    def _presentation_basename(self, pair_index: int, pair: EvalPair) -> str:
        stem = Path(pair.presentation_path).stem.replace(" ", "_")
        return f"{pair_index:04d}_{stem}"

    def _persist_success(self, pair_index: int, pair: EvalPair, evaluation: FullEvaluation) -> None:
        if not self._active_run_dir:
            return
        path = self._active_run_dir / f"{self._presentation_basename(pair_index, pair)}_evaluation.json"
        path.write_text(evaluation.model_dump_json(indent=2), encoding="utf-8")

    def _persist_failure(self, pair_index: int, pair: EvalPair, failure: FailedEvaluation) -> None:
        if not self._active_run_dir:
            return
        path = self._active_run_dir / f"{self._presentation_basename(pair_index, pair)}_failed.json"
        path.write_text(failure.model_dump_json(indent=2), encoding="utf-8")

    def _write_report(self, run_dir: Path, report: EvalBatchReport) -> None:
        report_path = run_dir / "report.json"
        report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    def _write_summary(self, run_dir: Path, report: EvalBatchReport) -> None:
        summary_path = run_dir / "summary.txt"
        lines = [
            f"Run ID: {report.run_id}",
            f"Total: {report.total_presentations}",
            f"Successful: {report.successful}",
            f"Failed: {report.failed}",
        ]
        if report.yaml_failures:
            lines.append("YAML failures:")
            lines.extend(report.yaml_failures)
        summary_path.write_text("\n".join(lines), encoding="utf-8")

    def _checkpoint_path(self, run_dir: Path) -> Path:
        return run_dir / "checkpoint.json"    def _load_checkpoint(self, run_dir: Path) -> Dict[str, Any]:
        path = self._checkpoint_path(run_dir)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}    def _save_checkpoint(self, run_dir: Path, completed_indices: set[int], failed_indices: set[int], yaml_failures: set[str]) -> None:
        payload = {
            "completed_indices": sorted(completed_indices),
            "failed_indices": sorted(failed_indices),
            "yaml_failures": sorted(yaml_failures),
        }
        path = self._checkpoint_path(run_dir)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")    def _load_completed_results(
        self,
        run_dir: Path,
        eval_pairs: Sequence[EvalPair],
        completed_indices: set[int],
        failed_indices: set[int],
    ) -> Tuple[List[EvaluationSuccess], List[FailedEvaluation]]:
        successes: List[EvaluationSuccess] = []
        failures: List[FailedEvaluation] = []
        for idx in completed_indices:
            if idx < 0 or idx >= len(eval_pairs):
                continue
            pair = eval_pairs[idx]
            eval_path = run_dir / f"{self._presentation_basename(idx, pair)}_evaluation.json"
            if not eval_path.exists():
                continue
            try:
                evaluation = FullEvaluation.model_validate_json(eval_path.read_text(encoding="utf-8"))
                golden = self.yaml_loader(Path(pair.metric_yaml_path))
                successes.append(EvaluationSuccess(pair=pair, golden=golden, evaluation=evaluation))
            except Exception:
                continue
        for idx in failed_indices:
            if idx < 0 or idx >= len(eval_pairs):
                continue
            pair = eval_pairs[idx]
            fail_path = run_dir / f"{self._presentation_basename(idx, pair)}_failed.json"
            if not fail_path.exists():
                continue
            try:
                failure = FailedEvaluation.model_validate_json(fail_path.read_text(encoding="utf-8"))
                failures.append(failure)
            except Exception:
                continue
        return successes, failures