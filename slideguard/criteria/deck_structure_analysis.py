from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo

prompt = """
You are an expert in evaluating the completeness of presentation structure.
You will be provided with information about all slides in the presentation.
Your task is to check whether the presentation contains key elements:
- First slide of the slide deck should contain 1) title of the presentation, 2) name and group number of the presenter, 3) name and place of work of scientific advisor, 4) date and place of presentation.
- The following elements should be present in the slide deck in the following order: 1) Motivation, 2) Goals, 3) Tasks, 4) Current State, 5) Proposed Solution, 6) Experiment Settings, 7) Experimental Results, 8) Conclusion.

If something of above is missing it is a strict violation of the slide deck structure and should be reported.

Write the result in the following JSON format:
{schema_format}
"""

class DeckStructureAnalysisResult(BaseModel):
    evaluation_element: str = Field(description="Evaluation element")
    evaluation_suggestion: str = Field(description="Evaluation suggestion")

class DeckStructureAnalysis(BaseModel):
    evaluation_results: list[DeckStructureAnalysisResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

deck_structure_analysis = CriterionInfo(
    criterion_name="Deck Structure Analysis",
    criterion_type="deck",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=DeckStructureAnalysis,
    applicable_slide_types=None,  # Applies to entire deck
    priority=1,
    requires_slide_type=True,  # Needs slide types to evaluate structure
    category="structure"
) 