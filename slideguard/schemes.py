from abc import ABC
from enum import Enum
import json
from typing import Any, Dict, Generic, List, Optional, TypeVar
from dataclasses import dataclass
from pydantic import BaseModel, Field
from slideguard.criteria.presentation_types import PresentationType

T = TypeVar('T', bound=BaseModel)

class Slideable(BaseModel):
    # None means deck-level criteria input
    slide_id: Optional[int] = None


class SlideImage(Slideable):
    slide_image_path: str

    class Config:
        frozen = True

class Criteria(str, Enum):
    # slide criteria
    slide_type = "slide_type"
    slide_description = "slide_description"
    slide_visual_arrangement = "slide_visual_arrangement"
    slide_color_and_fonts = "slide_color_and_fonts"
    slide_abbreviations = "slide_abbreviations"
    slide_fact_link_availability = "slide_fact_link_availability"
    slide_graphic_content_match = "slide_graphic_content_match"
    slide_orphography_correctness = "slide_orphography_correctness"
    slide_title_content_match = "slide_title_content_match"
    slide_title_slide_quality = "slide_title_slide_quality"
    slide_scientific_track_justification = "slide_scientific_track_justification"

    # deck criteria
    deck_storytelling = "deck_storytelling"
    deck_structure_analysis = "deck_structure_analysis"
    deck_research_quality = "deck_research_quality"

    def is_service_criteria(self) -> bool:
        return self in [self.slide_type, self.slide_description]
    
    def is_slide_criteria(self) -> bool:
        return self.value.startswith("slide_")
    
    def is_deck_criteria(self) -> bool:
        return self.value.startswith("deck_")


class SlideDescription(BaseModel):
    title: str = Field(description="Exact explicit slide title. If there is no clear title at the top of the slide, output 'No title' here")
    description: str = Field(description="Detailed description of the slide, including description of all charts, tables and illustrations and how they are arranged")
    summary: str = Field(description="Brief but comprehensive description of this individual slide")


class SlideType(BaseModel):
    slide_type: list[str] = Field(default_factory=list, description="List of slide types that are most suitable for the slide")
    contains_infographics: bool = Field(default=False, description="Whether the slide contains infographics")

class SlideDescriptionWithType(SlideDescription, SlideType):
    """Combines slide description with type and infographics information"""
    pass


# we inherit from Slideable to make it compatible with cache manager
class DeckDescription(Slideable):
    deck_description: str

    @staticmethod
    def from_slide_descriptions(slide_descriptions: List[SlideDescriptionWithType]) -> "DeckDescription":
        normalized = [
            {**slide.model_dump(), "slide_type": sorted(slide.slide_type)}
            for slide in slide_descriptions
        ] # canonicalize slide_type to be sorted for cache key
        return DeckDescription(deck_description=json.dumps(normalized, sort_keys=True, separators=(",", ":"), indent=4))

    class Config:
        frozen = True


class DeckEvaluationResult(BaseModel):
    """Result of a single criterion evaluation"""
    evaluations: Dict[Criteria, Any]


class SlideEvaluationResult(BaseModel):
    """Result of slide-level evaluation"""
    slide_deck_path: str
    slide_id: int
    slide_type: Optional[SlideType] = None
    slide_description: Optional[SlideDescription] = None
    evaluations: Optional[Dict[Criteria, Any]] = None


class FullEvaluation(BaseModel):
    """Result of deck-level evaluation"""
    slide_deck_path: str
    slide_evaluations: List[SlideEvaluationResult]
    deck_evaluations: Optional[DeckEvaluationResult] = None
    overall_score: Optional[int] = None
    summary: Optional[str] = None
    tldr: Optional[str] = None


class SummaryOutput(BaseModel):
    summary: str

class TLDROutput(BaseModel):
    tldr: str


class AbstractSlideDeck(ABC, BaseModel, Generic[T]):
    slide_deck_path: str
    slides: List[T]


class SlideDeckImages(AbstractSlideDeck[SlideImage]):
    png_dir: str


class SlideDeckDescriptions(AbstractSlideDeck[DeckDescription]):
    pass


@dataclass(frozen=True)
class UIEvaluationResult:
    deck_summary: str
    first_slide_image: Optional[str]
    tldr_html: str
    score_html: str
    status_msg: str

    @classmethod
    def error(cls, error_message: str) -> 'UIEvaluationResult':
        return cls(
            deck_summary=f"❌ {error_message}",
            first_slide_image=None,
            tldr_html="",
            score_html="",
            status_msg=f"❌ {error_message}"
        )
    
    def __iter__(self): #method for unpacking as tuple in gradio
        return iter((self.deck_summary, self.first_slide_image, self.tldr_html, self.score_html, self.status_msg))