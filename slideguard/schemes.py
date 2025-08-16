from abc import ABC
from enum import Enum
import json
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

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

    # deck criteria
    deck_storytelling = "deck_storytelling"
    deck_structure_analysis = "deck_structure_analysis"
    deck_research_quality = "deck_research_quality"

    def is_service_criteria(self) -> bool:
        return self in [self.slide_type, self.slide_description]


class SlideDescription(BaseModel):
    title: str = Field(description="Exact explicit slide title. If there is no clear title at the top of the slide, output 'No title' here")
    description: str = Field(description="Detailed description of the slide, including description of all charts, tables and illustrations and how they are arranged")
    summary: str = Field(description="Brief but comprehensive description of this individual slide")


class SlideType(BaseModel):
    slide_type: list[str] = Field(description="List of slide types that are most suitable for the slide")

class SlideDescriptionWithType(SlideDescription):
    slide_type: list[str] = Field(description="List of slide types that are most suitable for the slide")


# we inherit from Slideable to make it compatible with cache manager
class DeckDescription(Slideable):
    deck_description: str

    @staticmethod
    def from_slide_descriptions(slide_descriptions: List[SlideDescriptionWithType]) -> "DeckDescription":
        descriptions = json.dumps([slide.model_dump() for slide in slide_descriptions], indent=4)
        return DeckDescription(deck_description=descriptions)

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
    deck_evaluations: DeckEvaluationResult
    overall_score: Optional[float] = None
    summary: Optional[str] = None


class AbstractSlideDeck(ABC, BaseModel, Generic[T]):
    slide_deck_path: str
    slides: List[T]


class SlideDeckImages(AbstractSlideDeck[SlideImage]):
    png_dir: str


class SlideDeckDescriptions(AbstractSlideDeck[DeckDescription]):
    pass

