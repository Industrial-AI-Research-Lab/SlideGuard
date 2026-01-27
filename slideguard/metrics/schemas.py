from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from slideguard.schemes import Criteria


class NormalizedIssue(BaseModel):
    issue: str
    severity: int = Field(ge=1, le=3, default=1)
    suggestion: Optional[str] = None


class NormalizedSlideEntry(BaseModel):
    slide_id: int
    criteria: Criteria
    issues: List[NormalizedIssue] = Field(default_factory=list)
    applicability_override: bool = False


class NormalizedDeckEntry(BaseModel):
    criteria: Criteria
    issues: List[NormalizedIssue] = Field(default_factory=list)


class GoldenYAMLSchema(BaseModel):
    deck: Dict[Criteria, List[NormalizedIssue]] = Field(default_factory=dict)
    slides: List[NormalizedSlideEntry] = Field(default_factory=list)
    annotation_status: Optional[str] = None
    schema_version: str = "v1"


class EvalPair(BaseModel):
    presentation_path: str
    metric_yaml_path: str
    criteria_preset: str = "default"
    enabled: bool = True
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class EvalPairsConfig(BaseModel):
    pairs: List[EvalPair] = Field(default_factory=list)
    last_updated: Optional[datetime] = None


class FailedEvaluation(BaseModel):
    presentation_path: str
    error_type: str
    error_message: str
    traceback: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ConfusionEntry(BaseModel):
    presentation_path: str
    slide_id: Optional[int] = None
    criterion: Criteria
    predicted: bool
    ground_truth: bool
    label: str
    predicted_issues: List[str] = Field(default_factory=list)
    ground_truth_issues: List[str] = Field(default_factory=list)
    reason: Optional[str] = None


class MetricScores(BaseModel):
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    accuracy: float = 0.0


class CriterionMetrics(BaseModel):
    criterion: Criteria
    slide_metrics: Optional[MetricScores] = None
    deck_metrics: Optional[MetricScores] = None


class EvalBatchReport(BaseModel):
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    evaluator_version: Optional[str] = None
    config_hash: Optional[str] = None
    criteria_registry_hash: Optional[str] = None
    total_presentations: int
    successful: int
    failed: int
    failed_presentations: List[FailedEvaluation] = Field(default_factory=list)
    yaml_failures: List[str] = Field(default_factory=list)
    per_criterion_metrics: List[CriterionMetrics] = Field(default_factory=list)
    macro_avg_metrics: MetricScores
    micro_avg_metrics: MetricScores


class AtomicIssue(BaseModel):
    criterion: Criteria
    slide_ids: List[int] = Field(default_factory=list)
    issue_text: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    needs_review: bool = False


class FeedbackEntry(BaseModel):
    feedback_id: str
    feedback_text: str
    presentation_path: Optional[str] = None
    slide_id: Optional[int] = None
    criterion: Optional[Criteria] = None
    agreement: Optional[bool] = None
    comment: Optional[str] = None
    source: str = "cli"
    needs_review: bool = False
    timestamp: datetime = Field(default_factory=datetime.now(timezone.utc))
    user_id: Optional[str] = None
    feedback_hash: Optional[str] = None


class UnmappedFeedback(BaseModel):
    feedback_id: str
    presentation_path: Optional[str] = None
    issue_text: str
    reason: str
    timestamp: datetime = Field(default_factory=datetime.now(timezone.utc))


class FeedbackIssue(BaseModel):
    presentation_path: str
    criterion: Criteria
    slide_ids: List[int] = Field(default_factory=list)
    issue: NormalizedIssue

