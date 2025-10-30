from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable, Type
from pydantic import BaseModel, Field


class CriteriaTarget(str, Enum):
    slide = "slide"
    deck = "deck"


class OutputKind(str, Enum):
    scored_list = "scored_list"
    custom = "custom"


@runtime_checkable
class CriterionResultItem(Protocol):
    severity: int
    evaluation_element: str
    evaluation_suggestion: str


@runtime_checkable
class CriterionResult(Protocol):
    evaluation_results: List[CriterionResultItem]
    score: int


class PostProcessorContext(BaseModel):
    criteria_id: str
    params: Dict[str, Any] = Field(default_factory=dict)


PostProcessorFunc = Callable[[CriterionResult, PostProcessorContext], CriterionResult]


class Applicability(BaseModel):
    applicable_slide_types: Optional[List[str]] = None
    exclude_slide_types: Optional[List[str]] = None
    requires_infographics: bool = False


class ScoredListItemSpec(BaseModel):
    element_field_name: str = "evaluation_element"
    element_description: str = "Detected issue or observation"
    suggestion_field_name: str = "evaluation_suggestion"
    suggestion_description: str = "Actionable recommendation"
    extra_item_fields: Dict[str, Tuple[Type, Any]] = Field(default_factory=dict)
    score_min: int = 1
    score_max: int = 5


class OutputSpec(BaseModel):
    kind: OutputKind
    item_spec: Optional[ScoredListItemSpec] = None


