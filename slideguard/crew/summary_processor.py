"""
Summary processing utilities for SlideGuard evaluations.
"""

import json
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from collections import Counter, defaultdict
from statistics import mean
from pydantic import BaseModel
import logging

from slideguard.criteria.factory import CriteriaRegistry
from slideguard.schemes import (
    Criteria, SlideEvaluationResult, DeckEvaluationResult
)

logger = logging.getLogger(__name__)

@runtime_checkable
class ScoredEvaluation(Protocol):
    score: int

@runtime_checkable
class EvaluationWithResults(Protocol):
    evaluation_results: List[Any]

class SummaryConfig(BaseModel):
    context_severity_threshold: int = 2 #минимум severity, который попадает в контекст LLM (вход)
    max_strengths: int = 5 #сколько сильных сторон максимум добавляем в контекст
    strength_min_avg_score: int = 4 #порог средней оценки, чтобы вообще считать слайд сильной стороной

    max_items_per_criterion: int = 3 #максимум проблем, которые берём из одного критерия
    max_criteria_per_slide: int = 4 #максимум критериев, которые берём с одного слайда

    max_chars_element: int = 120 #режем текст проблемы (element) до этого числа символов
    max_chars_suggestion: int = 80 #режем suggestions (рекомендации) 0 = не передавать их вообще 
    max_chars_title: int = 80 #режем заголовок слайда
    max_chars_slide_summary: int = 120 #режем описание/summary слайда

    severity_top_k: int = 3 #в каждом критерии берём top-K находок по severity (сначала самые жёсткие)

    max_slides_in_summary: int = 25 #максимум слайдов, которые вообще попадут в саммаризацию
    summary_budget_tokens: int = 28000 #общий “лимит токенов” на summary-пейлоад (приблизительно)
    min_slide_tokens: int = 218 #минимальный бюджет токенов на один слайд при распределении
    chars_per_token: int = 2 #грубый перевод токены→символы для бюджетирования/обрезки

    severity_threshold: int = 1 #минимум severity, который показываем в финальном пдф
    max_problems: int = 50 #жёсткий потолок общего числа проблем в финальном пдф

class NavigationSummary(BaseModel):
    overview: Dict[str, Any]
    problems: List[Dict[str, Any]]
    strengths: List[Dict[str, Any]]


class BasicSummaryPayload(BaseModel):
    slide_evaluations: List[Dict[str, Any]]
    deck_evaluations: Optional[Dict[str, Any]] = None


class AdvancedSummaryPayload(BaseModel):
    nav: NavigationSummary
    slide_evaluations: List[Dict[str, Any]]
    deck_evaluations: Optional[Dict[str, Any]] = None


SUMMARY_AGENT_BACKSTORY = """You are an expert at synthesizing complex evaluation data into clear, actionable insights.
You take results from multiple specialized agents and create a coherent summary that
highlights key findings, identifies priority areas for improvement, and provides
an overall assessment score. Your summaries help presenters understand exactly
what needs to be improved and why."""


class SummaryProcessor:
    """Processes evaluation results into structured summaries and payloads."""

    def __init__(self, config: Optional[SummaryConfig] = None) -> None:
        self.config = config or SummaryConfig()

    
    def get_summary_payload(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        deck_evaluations: Optional[DeckEvaluationResult],
        registry: CriteriaRegistry,
        advanced: bool = False
    ) -> BasicSummaryPayload | AdvancedSummaryPayload:
        """
        Generate summary payload from evaluation results with data filtering.
        
        BASIC MODE (advanced=False):
        - Filtered slide/deck evaluations for summary generation
        - Removes low-severity items and unfit criteria for each slide
        
        ADVANCED MODE (advanced=True):
        - Everything from basic mode PLUS navigation header for llm:
        - Overview statistics of presentation (slide types, scores, severity histogram)
        - Problems sorted by priority (severity*problem_prevalence)
        - Strengths of presentation (criteria with high average scores, excluding stoplist)
        
        Args:
            slide_evaluations: List of slide-level evaluation results
            deck_evaluations: Optional deck-level evaluation results  
            advanced: If True, includes analytics and navigation data
            
        Returns:
            BasicSummaryPayload or AdvancedSummaryPayload based on "advanced" parameter
        """
        self.config = self._get_dynamic_thresholds(slide_evaluations, deck_evaluations)
        
        if advanced:
            return self._get_summary_payload_advanced(slide_evaluations, deck_evaluations, registry)
        else:
            return self._get_summary_payload_basic(slide_evaluations, deck_evaluations, registry)
        
    def _is_reasoning_garbage(self, text):
        if not isinstance(text, str):
            return False
        t = text.lstrip()
        if t.startswith("Thought"):
            return True
        if "Search for abbreviations" in t:
            return True
        return False
    
    def _clean_items(self, items):
        cleaned = []
        for it in items:
            elem = it.get("evaluation_element")
            sugg = it.get("evaluation_suggestion")
            if self._is_reasoning_garbage(elem) or self._is_reasoning_garbage(sugg):
                continue
            cleaned.append(it)
        return cleaned
    
    def calculate_overall_score(
        self, 
        slide_evaluations: List[SlideEvaluationResult], 
        deck_evaluations: Optional[DeckEvaluationResult]
    ) -> Optional[int]:
        """Calculate overall presentation score based on all evaluation results."""
        scores = []
        
        # Collect slide scores
        for slide in slide_evaluations:
            if slide.evaluations:
                scores.extend(v.score for v in slide.evaluations.values() if isinstance(v, ScoredEvaluation))
        
        # Collect deck scores
        if deck_evaluations and deck_evaluations.evaluations:
            scores.extend(v.score for v in deck_evaluations.evaluations.values() if isinstance(v, ScoredEvaluation))
        
        if not scores:
            return None
        
        avg = sum(scores) / len(scores)
        return int(avg + (avg % 1 > 0.7))
    
    def _select_top_slides(self, slides: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        max_slides = self.config.max_slides_in_summary
        if len(slides) <= max_slides:
            return slides

        def score_slide(slide: Dict[str, Any]) -> tuple[int, int]:
            evals = slide.get("evaluations") or {}
            severities: List[int] = []
            for evaluation in evals.values():
                for item in evaluation.get("evaluation_results") or []:
                    try:
                        sev = int(item.get("severity", 0))
                    except (TypeError, ValueError):
                        sev = 0
                    severities.append(sev)
            if not severities:
                return (0, 0)
            return (max(severities), len(severities))

        sorted_slides = sorted(slides, key=score_slide, reverse=True)
        return sorted_slides[:max_slides]
        
    def _slide_severity_aggregate(self, slide: SlideEvaluationResult, registry: CriteriaRegistry) -> Dict[str, int]:
        """Aggregate severity for weighting slide budgets."""
        total = 0
        max_sev = 0
        count = 0

        if not slide.evaluations:
            return {"total": 0, "max": 0, "count": 0}

        for crit, obj in slide.evaluations.items():
            if crit.is_service_criteria() or not self._is_criterion_applicable(slide, crit, registry):
                continue

            d = self._to_dict(obj)
            raw_items = d.get("evaluation_results") or []
            if not isinstance(raw_items, list):
                continue

            raw_items = self._clean_items(raw_items)
            for it in raw_items:
                try:
                    sev = int(it.get("severity", 0))
                except (TypeError, ValueError):
                    sev = 0

                if sev < int(self.config.context_severity_threshold):
                    continue

                total += sev
                count += 1
                if sev > max_sev:
                    max_sev = sev

        return {"total": total, "max": max_sev, "count": count}

    def _pick_slides_under_min_budget(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        registry: CriteriaRegistry,
        budget_tokens: int,
    ) -> List[SlideEvaluationResult]:
        """If there are too many slides to give each at least min_slide_tokens, keep the most severe ones."""
        min_tokens = int(self.config.min_slide_tokens)
        if min_tokens <= 0:
            return slide_evaluations

        max_slides = budget_tokens // min_tokens if budget_tokens > 0 else 0
        if len(slide_evaluations) <= max_slides:
            return slide_evaluations

        scored = []
        for idx, slide in enumerate(slide_evaluations):
            agg = self._slide_severity_aggregate(slide, registry)
            scored.append((agg["total"], agg["max"], agg["count"], idx, slide))

        scored.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
        picked = scored[:max_slides]
        picked.sort(key=lambda x: x[3])
        return [x[4] for x in picked]

    def _allocate_slide_token_budgets(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        registry: CriteriaRegistry,
        budget_tokens: int,
    ) -> List[int]:
        """Allocate a fixed token budget across slides: worst slides get more, all get at least min_slide_tokens."""
        n = len(slide_evaluations)
        if n == 0:
            return []

        min_tokens = int(self.config.min_slide_tokens)
        min_tokens = max(0, min_tokens)

        if budget_tokens <= 0:
            return [min_tokens] * n

        base_total = n * min_tokens
        if base_total > budget_tokens:
            min_tokens = max(0, budget_tokens // max(1, n))
            base_total = n * min_tokens

        remaining = max(0, budget_tokens - base_total)

        aggregates = [self._slide_severity_aggregate(slide, registry) for slide in slide_evaluations]
        weights = [max(0, agg["total"]) for agg in aggregates]
        sum_w = sum(weights)

        if sum_w <= 0:
            weights = [1] * n
            sum_w = n

        raw = [remaining * (w / sum_w) for w in weights]
        ints = [int(x) for x in raw]
        budgets = [min_tokens + i for i in ints]
        used = sum(budgets)
        leftover = max(0, budget_tokens - used)

        fracs = [(raw[i] - ints[i], i) for i in range(n)]
        fracs.sort(reverse=True)
        for _, i in fracs[:leftover]:
            budgets[i] += 1

        return budgets

    def _compute_per_slide_text_caps(self, char_budget: int, n_items: int) -> Dict[str, int]:
        """Translate per-slide budget to truncation caps for summary and evaluation elements."""
        structural = 220 + 40 * int(self.config.max_criteria_per_slide)
        usable = max(0, int(char_budget) - structural)

        summary_cap = max(0, min(int(self.config.max_chars_slide_summary), int(usable * 0.35)))
        summary_cap = max(80, summary_cap) if usable > 0 else 0
        summary_cap = min(summary_cap, 1500)

        remaining = max(0, usable - summary_cap)

        if n_items <= 0:
            element_cap = max(40, min(int(self.config.max_chars_element), remaining))
        else:
            per_item = remaining // n_items
            element_cap = max(40, min(int(self.config.max_chars_element), per_item))
            element_cap = min(element_cap, 1200)

        return {"summary_cap": summary_cap, "element_cap": element_cap}

    def _truncate_item_texts(self, item: Dict[str, Any], element_cap: int) -> Dict[str, Any]:
        elem = item.get("evaluation_element")
        sugg = item.get("evaluation_suggestion")

        if isinstance(elem, str):
            elem = self._strip_debug_reasoning(elem)
            item["evaluation_element"] = self._truncate(elem, element_cap) if element_cap > 0 else None

        if self.config.max_chars_suggestion <= 0:
            item.pop("evaluation_suggestion", None)
        else:
            if isinstance(sugg, str):
                sugg = self._strip_debug_reasoning(sugg)
                item["evaluation_suggestion"] = self._truncate(sugg, int(self.config.max_chars_suggestion))

        return item

    def _filter_slide_evaluations_budgeted(
        self,
        slide: SlideEvaluationResult,
        registry: CriteriaRegistry,
        char_budget: int,
    ) -> Dict[str, Any]:
        evals: Dict[str, Any] = {}

        if slide.evaluations:
            for crit, obj in slide.evaluations.items():
                if crit.is_service_criteria() or not self._is_criterion_applicable(slide, crit, registry):
                    continue

                d = self._to_dict(obj)
                if d.get("evaluation_results"):
                    raw_items = d.get("evaluation_results") or []
                    raw_items = self._clean_items(raw_items)
                    filtered = self._filter_by_severity(raw_items, self.config.context_severity_threshold)
                    selected = self._select_items_by_severity(filtered, k=self.config.severity_top_k)
                    d["evaluation_results"] = selected

                if d.get("evaluation_results") or d.get("score"):
                    evals[str(crit)] = d

        if int(self.config.max_criteria_per_slide) > 0 and len(evals) > int(self.config.max_criteria_per_slide):
            crit_items = []
            for k, v in evals.items():
                severities = []
                for it in v.get("evaluation_results") or []:
                    try:
                        severities.append(int(it.get("severity", 0)))
                    except (TypeError, ValueError):
                        severities.append(0)
                max_sev = max(severities) if severities else 0
                crit_items.append((max_sev, len(severities), k, v))
            crit_items.sort(key=lambda x: (x[0], x[1]), reverse=True)
            evals = {k: v for _, _, k, v in crit_items[: int(self.config.max_criteria_per_slide)]}

        n_items = 0
        for v in evals.values():
            n_items += len(v.get("evaluation_results") or [])

        caps = self._compute_per_slide_text_caps(char_budget, n_items)

        for v in evals.values():
            if v.get("evaluation_results"):
                trimmed = []
                for it in v["evaluation_results"]:
                    if not isinstance(it, dict):
                        it = dict(it)
                    trimmed.append(self._truncate_item_texts(it, caps["element_cap"]))
                v["evaluation_results"] = trimmed

            if self.config.max_chars_suggestion <= 0 and v.get("evaluation_suggestion"):
                v.pop("evaluation_suggestion", None)

        desc = None
        if slide.slide_description:
            sd = slide.slide_description.model_dump()
            title = self._truncate(sd.get("title"), int(self.config.max_chars_title))
            summary = self._truncate(sd.get("summary"), caps["summary_cap"])
            desc = {"title": title, "summary": summary}

        return {
            "slide_id": slide.slide_id,
            "slide_type": slide.slide_type.model_dump() if slide.slide_type else "unknown",
            "slide_description": desc,
            "evaluations": evals,
        }

    def _build_budgeted_slide_summaries(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        registry: CriteriaRegistry,
        budget_tokens: int,
    ) -> List[Dict[str, Any]]:
        if not slide_evaluations:
            return []

        picked = self._pick_slides_under_min_budget(slide_evaluations, registry, budget_tokens)
        token_budgets = self._allocate_slide_token_budgets(picked, registry, budget_tokens)

        slide_summaries: List[Dict[str, Any]] = []
        for slide, t in zip(picked, token_budgets):
            char_budget = int(t) * int(self.config.chars_per_token)
            slide_summaries.append(self._filter_slide_evaluations_budgeted(slide, registry, char_budget))

        return slide_summaries

    def _truncate_deck_items(self, items: List[Dict[str, Any]], max_chars_element: int) -> List[Dict[str, Any]]:
        out = []
        for it in items or []:
            if not isinstance(it, dict):
                it = dict(it)
            elem = it.get("evaluation_element")
            if isinstance(elem, str):
                elem = self._strip_debug_reasoning(elem)
                it["evaluation_element"] = self._truncate(elem, max_chars_element)
            if self.config.max_chars_suggestion <= 0:
                it.pop("evaluation_suggestion", None)
            out.append(it)
        return out

    def _enforce_total_payload_budget(self, payload_data: Dict[str, Any], budget_chars: int) -> None:
        """Hard guard: shrink texts and/or drop best slides until payload fits budget."""
        if budget_chars <= 0:
            payload_data["slide_evaluations"] = []
            return

        def payload_len() -> int:
            try:
                return len(json.dumps(payload_data, ensure_ascii=False, separators=(",", ":")))
            except Exception:
                return len(json.dumps(payload_data))

        for factor in (0.75, 0.75, 0.75):
            if payload_len() <= budget_chars:
                return
            self._shrink_payload_texts_in_place(payload_data, factor)

        slides = payload_data.get("slide_evaluations") or []
        while slides and payload_len() > budget_chars:
            scored = []
            for idx, s in enumerate(slides):
                bad = 0
                for ev in (s.get("evaluations") or {}).values():
                    for it in ev.get("evaluation_results") or []:
                        try:
                            bad += int(it.get("severity", 0))
                        except (TypeError, ValueError):
                            pass
                scored.append((bad, idx))
            scored.sort(key=lambda x: x[0])
            _, drop_idx = scored[0]
            slides.pop(drop_idx)

        payload_data["slide_evaluations"] = slides

    def _shrink_payload_texts_in_place(self, payload_data: Dict[str, Any], factor: float) -> None:
        slides = payload_data.get("slide_evaluations") or []
        for s in slides:
            desc = s.get("slide_description")
            if isinstance(desc, dict):
                for k in ("title", "summary"):
                    v = desc.get(k)
                    if isinstance(v, str) and len(v) > 30:
                        new_len = max(30, int(len(v) * factor))
                        desc[k] = v if len(v) <= new_len else (v[: new_len - 1] + "…")

            evals = s.get("evaluations") or {}
            for ev in evals.values():
                if not isinstance(ev, dict):
                    continue
                for it in ev.get("evaluation_results") or []:
                    if not isinstance(it, dict):
                        continue
                    elem = it.get("evaluation_element")
                    if isinstance(elem, str) and len(elem) > 30:
                        new_len = max(30, int(len(elem) * factor))
                        it["evaluation_element"] = elem if len(elem) <= new_len else (elem[: new_len - 1] + "…")

        deck = payload_data.get("deck_evaluations")
        if isinstance(deck, dict):
            evals = deck.get("evaluations") or {}
            if isinstance(evals, dict):
                for ev in evals.values():
                    if not isinstance(ev, dict):
                        continue
                    for it in ev.get("evaluation_results") or []:
                        if not isinstance(it, dict):
                            continue
                        elem = it.get("evaluation_element")
                        if isinstance(elem, str) and len(elem) > 30:
                            new_len = max(30, int(len(elem) * factor))
                            it["evaluation_element"] = elem if len(elem) <= new_len else (elem[: new_len - 1] + "…")
    DEBUG_MARKERS = (
        "Thought",
        "1. Search for abbreviations",
        "Шаг 1.",   # если начнёшь видеть русские варианты
    )

    def _strip_debug_reasoning(self, text: str | None) -> str | None:
        """
        Режем внутренний reasoning (Thought / пошаговый анализ),
        который иногда модель зачем-то кладёт в evaluation_element.
        """
        if not isinstance(text, str):
            return text

        cleaned = text
        for marker in self.DEBUG_MARKERS:
            idx = cleaned.find(marker)
            if idx != -1:
                cleaned = cleaned[:idx].strip()
                break

        # если после вырезания вообще ничего не осталось — считаем,
        # что нормального текста не было
        return cleaned or None
    
    def _filter_by_severity(self, items: list[dict], threshold: int) -> list[dict]:
        out: list[dict] = []
        for it in items:
            try:
                sev = int(it.get("severity", 0))
            except (TypeError, ValueError):
                sev = 0
            if sev >= threshold:
                out.append(it)
        return out
    
    def _get_summary_payload_basic(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        deck_evaluations: Optional[DeckEvaluationResult],
        registry: CriteriaRegistry,
    ) -> BasicSummaryPayload:
        # Hard budget (tokens -> chars) reserved for slide summaries passed into the deck summarizer.
        budget_tokens = max(0, int(self.config.summary_budget_tokens))
        budget_chars = budget_tokens * int(self.config.chars_per_token)

        slide_summaries = self._build_budgeted_slide_summaries(slide_evaluations, registry, budget_tokens)

        payload_data: Dict[str, Any] = {"slide_evaluations": slide_summaries}

        if deck_evaluations:
            deck_dump = deck_evaluations.model_dump()
            for v in deck_dump.get("evaluations", {}).values():
                if v.get("evaluation_results"):
                    raw_items = v.get("evaluation_results") or []
                    raw_items = self._clean_items(raw_items)
                    filtered = self._filter_by_severity(raw_items, self.config.context_severity_threshold)
                    selected = self._select_items_by_severity(filtered, k=self.config.severity_top_k)
                    v["evaluation_results"] = self._truncate_deck_items(selected, max_chars_element=min(self.config.max_chars_element, 120))

                if self.config.max_chars_suggestion <= 0 and v.get("evaluation_suggestion"):
                    v.pop("evaluation_suggestion", None)

            payload_data["deck_evaluations"] = deck_dump

        # Final guard: never exceed the configured summary budget.
        self._enforce_total_payload_budget(payload_data, budget_chars)

        return BasicSummaryPayload(**payload_data)
    
    def _get_dynamic_thresholds(
        self, 
        slide_evaluations: List[SlideEvaluationResult], 
        deck_evaluations: Optional[DeckEvaluationResult]
    ) -> SummaryConfig:
        base_config = SummaryConfig()

        severities: List[int] = []
        for slide in slide_evaluations:
            if slide.evaluations:
                for evaluation in slide.evaluations.values():
                    if isinstance(evaluation, EvaluationWithResults):
                        severities.extend(item.severity for item in evaluation.evaluation_results)

        if deck_evaluations and deck_evaluations.evaluations:
            for evaluation in deck_evaluations.evaluations.values():
                if isinstance(evaluation, EvaluationWithResults):
                    severities.extend(item.severity for item in evaluation.evaluation_results)

        slide_count = len(slide_evaluations)
        if slide_count > 80:
            base_config.context_severity_threshold = 3
            base_config.max_items_per_criterion = 2
            base_config.max_slides_in_summary = 40
        elif slide_count > 40:
            base_config.context_severity_threshold = 2
            base_config.max_items_per_criterion = 3
            base_config.max_slides_in_summary = 50

        if severities and sum(s >= base_config.severity_threshold for s in severities) / len(severities) < 0.1:
            target_severity = sorted(severities, reverse=True)[int(len(severities) * 0.5) - 1]
            return SummaryConfig(
                context_severity_threshold=max(1, target_severity - 1),
                severity_threshold=target_severity,
                max_problems=base_config.max_problems,
                max_strengths=base_config.max_strengths,
                strength_min_avg_score=base_config.strength_min_avg_score,
                max_items_per_criterion=base_config.max_items_per_criterion,
                max_slides_in_summary=base_config.max_slides_in_summary,
                max_chars_element=base_config.max_chars_element,
                max_chars_suggestion=base_config.max_chars_suggestion,
            )

        return base_config
        base_config = SummaryConfig()
        
        se
    
    
    def _select_items_by_severity(self, items: list[dict], k: int | None) -> list[dict]:
        if not items:
            return []

        norm_items: list[dict] = []
        for it in items:
            try:
                sev = int(it.get("severity", 0))
            except (TypeError, ValueError):
                sev = 0
            it = dict(it)
            it["_sev_int"] = sev
            norm_items.append(it)

        if not norm_items:
            return []

        max_sev = max(it["_sev_int"] for it in norm_items)
        primary = [it for it in norm_items if it["_sev_int"] == max_sev]

        result = primary

        if k is not None and k > 0 and len(result) < k:
            rest = [it for it in norm_items if it["_sev_int"] < max_sev]
            rest.sort(key=lambda x: x["_sev_int"], reverse=True)
            need = k - len(result)
            result = result + rest[:need]

        max_total = getattr(self.config, "max_items_per_criterion", None)
        if max_total is not None and max_total > 0 and len(result) > max_total:
            result = result[:max_total]

        cleaned: list[dict] = []
        for it in result:
            it = dict(it)
            it.pop("_sev_int", None)
            cleaned.append(it)

        return cleaned
    
    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert object to dictionary representation."""
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        else:
            return json.loads(
                json.dumps(obj, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o)))
    
    def _is_criterion_applicable(self, slide: SlideEvaluationResult, criterion: Criteria, registry: CriteriaRegistry) -> bool:
        """Check if a criterion is applicable to a specific slide."""
        info = registry.get_info(criterion)
        if not info.applicable_slide_types:
            return True
        
        types = slide.slide_type.slide_type if (slide.slide_type and slide.slide_type.slide_type) else []
        return any(t in info.applicable_slide_types for t in types)
    
    def _truncate(self, text: Optional[str], max_len: int) -> Optional[str]:
        if not isinstance(text, str):
            return text
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"


    def _compress_items(self, items: list[dict]) -> list[dict]:
        kept: list[dict] = []
        for it in items:
            sev = int(it.get("severity", 0))
            elem = it.get("evaluation_element")
            sugg = it.get("evaluation_suggestion")

            elem = self._strip_debug_reasoning(elem)
            sugg = self._strip_debug_reasoning(sugg)

            elem = self._truncate(elem, self.config.max_chars_element)
            sugg = self._truncate(sugg, self.config.max_chars_suggestion)

            kept.append(
                {
                    "severity": sev,
                    "evaluation_element": elem,
                    "evaluation_suggestion": sugg,
                }
            )

        kept.sort(key=lambda x: x["severity"], reverse=True)
        return kept[: self.config.max_items_per_criterion]

    def _filter_slide_evaluations(self, slide: SlideEvaluationResult, registry: CriteriaRegistry) -> Dict[str, Any]:
        evals: Dict[str, Any] = {}

        if slide.evaluations:
            for crit, obj in slide.evaluations.items():
                if crit.is_service_criteria() or not self._is_criterion_applicable(slide, crit, registry):
                    continue

                d = self._to_dict(obj)
                if d.get("evaluation_results"):
                    raw_items = d.get("evaluation_results") or []
                    raw_items = self._clean_items(raw_items)
                    filtered = self._filter_by_severity(raw_items, self.config.context_severity_threshold)
                    selected = self._select_items_by_severity(filtered, k=self.config.severity_top_k)
                    d["evaluation_results"] = selected

                if d.get("evaluation_results") or d.get("score"):
                    evals[str(crit)] = d

        desc = None
        if slide.slide_description:
            sd = slide.slide_description.model_dump()
            desc = {
                "title": sd.get("title"),
                "summary": sd.get("summary"),
            }

        return {
            "slide_id": slide.slide_id,
            "slide_type": slide.slide_type.model_dump() if slide.slide_type else "unknown",
            "slide_description": desc,
            "evaluations": evals,
        }
    
    # Advanced payload methods
    
    def _get_summary_payload_advanced(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        deck_evaluations: Optional[DeckEvaluationResult],
        registry: CriteriaRegistry,
    ) -> AdvancedSummaryPayload:
        """Generate advanced summary payload with analytics and navigation data."""
        basic_payload = self._get_summary_payload_basic(slide_evaluations, deck_evaluations, registry)
        
        # Extract slide types and count them
        slide_types = [self._extract_slide_type(s) for s in basic_payload.slide_evaluations]
        type_counts = Counter(slide_types)


        # Calculate average scores
        avg_scores = self._calculate_avg_scores(basic_payload)
        
        # Count severity histogram
        sev_histogram = self._calculate_severity_histogram(basic_payload)
        
        # Analyze problems and strengths
        problems, strengths = self._analyze_problems_and_strengths(slide_evaluations, deck_evaluations, avg_scores)
        
        overview = {
            "total_slides": len(basic_payload.slide_evaluations),
            "slide_types_distribution": dict(type_counts),
            "avg_scores": avg_scores,
            "severity_histogram": sev_histogram
        }
        
        navigation = NavigationSummary(overview=overview, problems=problems, strengths=strengths)
        
        return AdvancedSummaryPayload(
            nav=navigation,
            slide_evaluations=basic_payload.slide_evaluations,
            deck_evaluations=basic_payload.deck_evaluations
        )
    
    def _extract_slide_type(self, slide_data: Dict[str, Any]) -> str:
        """Extract slide type from slide data."""
        slide_type = slide_data.get('slide_type', 'unknown')
        if isinstance(slide_type, dict) and 'slide_type' in slide_type:
            return slide_type['slide_type'][0] if slide_type['slide_type'] else 'unknown'
        return 'unknown'
    
    def _calculate_avg_scores(self, payload: BasicSummaryPayload) -> Dict[str, float]:
        """Calculate average scores from payload."""
        score_lists = defaultdict(list)
        
        # Collect slide scores
        for slide in payload.slide_evaluations:
            for key, evaluation in slide.get('evaluations', {}).items():
                if isinstance(evaluation, dict) and 'score' in evaluation:
                    score_lists[key].append(evaluation['score'])
        
        # Collect deck scores
        if payload.deck_evaluations:
            for key, evaluation in payload.deck_evaluations.get('evaluations', {}).items():
                if isinstance(evaluation, dict) and 'score' in evaluation:
                    score_lists[key].append(evaluation['score'])
        
        return {key: round(mean(scores), 2) for key, scores in score_lists.items() if scores}
    
    def _calculate_severity_histogram(self, payload: BasicSummaryPayload) -> Dict[str, int]:
        """Calculate severity histogram from payload."""
        sev_counts = Counter()
        
        # Count slide severities
        for slide in payload.slide_evaluations:
            for evaluation in slide.get('evaluations', {}).values():
                if isinstance(evaluation, dict) and 'evaluation_results' in evaluation:
                    for item in evaluation['evaluation_results']:
                        if isinstance(item, dict) and 'severity' in item:
                            sev_counts[str(item['severity'])] += 1
        
        # Count deck severities
        if payload.deck_evaluations:
            for evaluation in payload.deck_evaluations.get('evaluations', {}).values():
                if isinstance(evaluation, dict) and 'evaluation_results' in evaluation:
                    for item in evaluation['evaluation_results']:
                        if isinstance(item, dict) and 'severity' in item:
                            sev_counts[str(item['severity'])] += 1
        
        return {str(i): sev_counts.get(str(i), 0) for i in range(1, 6)}
    
    def _analyze_problems_and_strengths(
        self,
        slide_evaluations: List[SlideEvaluationResult],
        deck_evaluations: Optional[DeckEvaluationResult],
        avg_scores: Dict[str, float]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Analyze problems and strengths from evaluation results.
        
        STRENGTHS GENERATION LOGIC:
        1. Iterate through all criteria average scores
        2. Include criterion as strength if:
           - Average score >= cfg.strength_min_avg_score
           - Criterion is NOT in stoplist (excludes noisy/less meaningful criteria)
        3. Limit to cfg.max_strengths best performing criteria
        
        PROBLEMS GENERATION LOGIC:
        1. SLIDE PROBLEMS:
           - For each slide evaluation, collect statistics per criterion:
             * count: Total slides evaluated for this criterion
             * problem_count: Slides with severe issues (severity >= threshold)
             * avg_severity: Average severity for this criterion
           - Calculate priority score for each criterion:
             Priority = 100 * (avg_severity/5.0) * (problem_prevalence)
             Where:
             * problem_prevalence = problem_count / max(1, count) (% of slides affected)
           - Sort by priority (higher = more critical)
        
        2. DECK PROBLEMS:
           - For each deck criterion with severe issues (severity >= threshold):
           - Calculate priority = 100 * (avg_severity/5.0)
           - Sort by priority (higher = more critical)
        
        3. PROBLEM COMBINATION:
           - Take top half of max_problems from slide problems
           - Take top half of max_problems from deck problems  
           - Combine up to max_problems total
           - Fill remaining slots with next best problems from either category
        
        SEVERITY THRESHOLD:
        - Dynamically calculated based on distribution (default: 3/5)
        - Only issues >= threshold are considered "problems"
        """
        criteria_stoplist = {"slide_title_content_match", "slide_orphography_correctness", "slide_title_slide_quality", "slide_abbreviations"}
        
        # Generate strengths: criteria with high average scores, excluding stoplist
        strengths = [{"criterion": k} for k, v in avg_scores.items() 
                    if v >= self.config.strength_min_avg_score and k not in criteria_stoplist][:self.config.max_strengths]
        
        # Generate problems based on severity analysis
        problems = []
        threshold = int(self.config.severity_threshold)
        
        # Analyze slide problems: collect statistics per criterion
        slide_stats = defaultdict(lambda: [0, 0, 0, 0])  # [count, problem_count, severity_sum, severity_count]
        for s in slide_evaluations:
            if s.evaluations:
                for crit, ev in s.evaluations.items():
                    if crit.is_service_criteria():
                        continue
                    key = crit.value
                    if isinstance(ev, EvaluationWithResults):
                        severe_items = [it.severity for it in ev.evaluation_results if it.severity >= threshold]
                        slide_stats[key][0] += 1  # Total slides for this criterion
                        if severe_items:
                            slide_stats[key][1] += 1  # Slides with problems
                            slide_stats[key][2] += sum(severe_items)  # Sum of severities
                            slide_stats[key][3] += len(severe_items)  # Count of severe items
        
        # Calculate slide problem priorities: priority = 100 * (avg_severity/5.0) * (problem_prevalence)
        slide_problems = [{"criterion": k, "priority": int(100 * ((sm / n) / 5.0) * (p / max(1, c)))} 
                         for k, (c, p, sm, n) in slide_stats.items() if p and n]
        slide_problems.sort(key=lambda x: x["priority"], reverse=True)
        
        # Analyze deck problems: simpler priority based on average severity
        deck_problems = []
        if deck_evaluations:
            for crit, ev in deck_evaluations.evaluations.items():
                if isinstance(ev, EvaluationWithResults):
                    severe_items = [it.severity for it in ev.evaluation_results if it.severity >= threshold]
                    if severe_items:
                        deck_problems.append({
                            "criterion": crit.value,
                            "priority": int(100 * ((sum(severe_items) / len(severe_items)) / 5.0))
                        })
        deck_problems.sort(key=lambda x: x["priority"], reverse=True)
        
        # Combine problems: balanced approach between slide and deck issues
        max_problems = int(self.config.max_problems)
        half = max_problems // 2
        problems = (slide_problems[:half] + deck_problems[:half])[:max_problems]
        remaining = max_problems - len(problems)
        if remaining > 0:
            problems += (slide_problems[half:] + deck_problems[half:])[:remaining]
        
        return problems, strengths
