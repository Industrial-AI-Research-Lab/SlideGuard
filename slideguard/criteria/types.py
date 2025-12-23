from enum import Enum
import logging
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, runtime_checkable, Type, Union
from pydantic import BaseModel, Field, field_validator


class CriteriaTarget(str, Enum):
    slide = "slide"
    deck = "deck"


class PresentationType(str, Enum):
    collaborative = "collaborative"
    industrial = "industrial"
    scientific = "scientific"
    technological = "technological"


ALL_PRESENTATION_TYPES: List[str] = [p.value for p in PresentationType]
DEFAULT_PRESENTATION_TYPE: str = PresentationType.scientific.value


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
    presentation_types: Optional[List[str]] = None

    @field_validator('applicable_slide_types', 'exclude_slide_types', 'presentation_types', mode='before')
    @classmethod
    def convert_enum_to_string(cls, v: Optional[List[Union[str, Enum]]]) -> Optional[List[str]]:
        """Convert enum values to their string representations."""
        if v is None:
            return None
        out: List[str] = []
        for item in v:
            try:
                out.append(item.value)
            except AttributeError:
                logging.warning(f"Wrong slide type passed in config: {item}. Converting to string directly, which could lead to unexpected behavior")
                out.append(str(item))
        return out


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


