from pydantic import BaseModel, Field
from slideguard.criteria_info.base import CriterionInfo

prompt = """
You are an expert in presentation structure analysis. You are provided with a complete slide deck.
Analyze the overall structure, flow, and organization of the presentation.

Evaluate the following aspects:
1. **Narrative Flow**: How well the story progresses from slide to slide
2. **Logical Structure**: Organization and hierarchy of information
3. **Content Balance**: Distribution of content across slides
4. **Transitions**: How well slides connect to each other
5. **Audience Journey**: How the presentation guides the audience

Provide a comprehensive analysis of the deck's structural quality and coherence.
"""

class DeckStructureAnalysis(BaseModel):
    narrative_flow_score: int = Field(description="Score from 1-10 for narrative flow", ge=1, le=10)
    logical_structure_score: int = Field(description="Score from 1-10 for logical structure", ge=1, le=10)
    content_balance_score: int = Field(description="Score from 1-10 for content balance", ge=1, le=10)
    transitions_score: int = Field(description="Score from 1-10 for slide transitions", ge=1, le=10)
    audience_journey_score: int = Field(description="Score from 1-10 for audience journey", ge=1, le=10)
    overall_structure_score: int = Field(description="Overall structure score from 1-10", ge=1, le=10)
    structure_analysis: str = Field(description="Detailed analysis of deck structure and flow")
    improvement_suggestions: str = Field(description="Specific suggestions for improving deck structure")

deck_structure_analysis = CriterionInfo(
    criterion_name="Deck Structure Analysis",
    criterion_type="deck",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=DeckStructureAnalysis
) 