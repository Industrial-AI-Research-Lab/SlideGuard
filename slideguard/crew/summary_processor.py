"""
Summary processing utilities for SlideGuard evaluations.
"""

import json
from typing import Any, Dict, List, Optional
from collections import Counter, defaultdict
from statistics import mean
from pydantic import BaseModel

from slideguard.criteria import SLIDE_CRITERIA_INFO
from slideguard.schemes import (
    Criteria, SlideEvaluationResult, DeckEvaluationResult
)

class SummaryConfig(BaseModel):
    context_severity_threshold: int = 2
    severity_threshold: int = 3
    max_problems: int = 10
    max_strengths: int = 5
    strength_min_avg_score: int = 4


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
    
    def get_summary_payload(
        self, 
        slide_evaluations: List[SlideEvaluationResult], 
        deck_evaluations: Optional[DeckEvaluationResult],
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
            return self._get_summary_payload_advanced(slide_evaluations, deck_evaluations)
        else:
            return self._get_summary_payload_basic(slide_evaluations, deck_evaluations)
    
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
                scores.extend(v.score for v in slide.evaluations.values() if hasattr(v, 'score'))
        
        # Collect deck scores
        if deck_evaluations and deck_evaluations.evaluations:
            scores.extend(v.score for v in deck_evaluations.evaluations.values() if hasattr(v, 'score'))
        
        if not scores:
            return None
        
        avg = sum(scores) / len(scores)
        return int(avg + (avg % 1 > 0.7))
    
    def _get_summary_payload_basic(
        self, 
        slide_evaluations: List[SlideEvaluationResult], 
        deck_evaluations: Optional[DeckEvaluationResult]
    ) -> BasicSummaryPayload:
        """Generate basic summary payload with filtered evaluation results."""
        slide_summaries = [self._filter_slide_evaluations(slide) for slide in slide_evaluations]
        payload_data = {"slide_evaluations": slide_summaries}
        
        if deck_evaluations:
            deck_dump = deck_evaluations.model_dump()
            for v in deck_dump.get('evaluations', {}).values():
                if v.get('evaluation_results'):
                    v['evaluation_results'] = self._filter_by_severity(v['evaluation_results'], self.config.context_severity_threshold)
            payload_data["deck_evaluations"] = deck_dump
        
        return BasicSummaryPayload(**payload_data)
    
    def _get_dynamic_thresholds(
        self, 
        slide_evaluations: List[SlideEvaluationResult], 
        deck_evaluations: Optional[DeckEvaluationResult]
    ) -> SummaryConfig:
        """Calculate dynamic thresholds based on severity distribution."""
        base_config = SummaryConfig()
        
        severities = [
            item.severity for slide in slide_evaluations if slide.evaluations
            for evaluation in slide.evaluations.values()
            for item in getattr(evaluation, 'evaluation_results', [])
        ]
        
        if deck_evaluations:
            severities.extend([
                item.severity for evaluation in deck_evaluations.evaluations.values()
                for item in getattr(evaluation, 'evaluation_results', [])
            ])
        
        # Adjust thresholds if less than 10% of items are severe
        if severities and sum(s >= base_config.severity_threshold for s in severities) / len(severities) < 0.1:
            target_severity = sorted(severities, reverse=True)[int(len(severities) * 0.5) - 1]
            return SummaryConfig(
                context_severity_threshold=max(1, target_severity - 1),
                severity_threshold=target_severity,
                max_problems=base_config.max_problems,
                max_strengths=base_config.max_strengths,
                strength_min_avg_score=base_config.strength_min_avg_score
            )
        
        return base_config
    
    def _filter_by_severity(self, items: List[Dict[str, Any]], min_severity: int) -> List[Dict[str, Any]]:
        """Filter evaluation items by minimum severity level."""
        return [item for item in items if int(item.get('severity', 0)) >= min_severity]
    
    def _to_dict(self, obj: Any) -> Dict[str, Any]:
        """Convert object to dictionary representation."""
        return obj.model_dump() if hasattr(obj, 'model_dump') else json.loads(
            json.dumps(obj, default=lambda o: getattr(o, '__dict__', str(o)))
        )
    
    def _is_criterion_applicable(self, slide: SlideEvaluationResult, criterion: Criteria) -> bool:
        """Check if a criterion is applicable to a specific slide."""
        if criterion == Criteria.slide_title_slide_quality:
            return bool(
                slide.slide_type and slide.slide_type.slide_type and 
                ('Title slide' in slide.slide_type.slide_type)
            )
        
        info = SLIDE_CRITERIA_INFO.get(criterion)
        if not info or not getattr(info, 'applicable_slide_types', None):
            return True
        
        types = slide.slide_type.slide_type if (slide.slide_type and slide.slide_type.slide_type) else []
        return any(t in info.applicable_slide_types for t in types)
    
    def _filter_slide_evaluations(self, slide: SlideEvaluationResult) -> Dict[str, Any]:
        """Filter and format slide evaluations based on configuration."""
        evals = {}
        
        if slide.evaluations:
            for crit, obj in slide.evaluations.items():
                if crit.is_service_criteria() or not self._is_criterion_applicable(slide, crit):
                    continue
                
                d = self._to_dict(obj)
                if d.get('evaluation_results'):
                    d['evaluation_results'] = self._filter_by_severity(d['evaluation_results'], self.config.context_severity_threshold)
                
                if d.get('evaluation_results') or d.get('score'):
                    evals[str(crit)] = d
        
        return {
            "slide_id": slide.slide_id,
            "slide_type": slide.slide_type.model_dump() if slide.slide_type else "unknown",
            "slide_description": slide.slide_description.model_dump() if slide.slide_description else "not found",
            "evaluations": evals
        }
    
    # Advanced payload methods
    
    def _get_summary_payload_advanced(
        self, 
        slide_evaluations: List[SlideEvaluationResult], 
        deck_evaluations: Optional[DeckEvaluationResult]
    ) -> AdvancedSummaryPayload:
        """Generate advanced summary payload with analytics and navigation data."""
        basic_payload = self._get_summary_payload_basic(slide_evaluations, deck_evaluations)
        
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
                    if hasattr(crit, 'is_service_criteria') and crit.is_service_criteria():
                        continue
                    key = crit.value if hasattr(crit, 'value') else str(crit)
                    if hasattr(ev, 'evaluation_results'):
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
                if hasattr(ev, 'evaluation_results'):
                    severe_items = [it.severity for it in ev.evaluation_results if it.severity >= threshold]
                    if severe_items:
                        deck_problems.append({
                            "criterion": crit.value if hasattr(crit, 'value') else str(crit),
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
