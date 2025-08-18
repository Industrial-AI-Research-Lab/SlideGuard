from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_DECK_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in evaluating the completeness of presentation structure.
You will be provided with information about all slides in the presentation.
Your task is to check whether the presentation contains all the key structural elements.

## Key Structural Elements to Evaluate:
- The following elements should be present in the slide deck in the following order: 1) Title slide, 2) Separator slide, 3) Motivation, 4) Goals, 5) Tasks, 6) Current State, 7) Proposed Solution, 8) Experiment Settings, 9) Experimental Results, 10) Conclusion, 11) End slide.

## Common Problems to Identify:
- Absence of structural elements
- Incorrect order of structural elements

## What is not a problem:
- Some presentations may have extra slides after the last slide, which is not a problem

If something of above is missing it is a strict violation of the slide deck structure and should be reported.

## Response Format:
The result should be in the following JSON format:
{schema_format}
"""


class DeckStructureAnalysisResult(BaseAttributes):
    evaluation_element: str = Field(description="Evaluation element")
    evaluation_suggestion: str = Field(description="Evaluation suggestion")


class DeckStructureAnalysis(BaseModel):
    evaluation_results: list[DeckStructureAnalysisResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5")


DECK_STRUCTURE_ANALYSIS = CriterionInfo(
    criteria=Criteria.deck_structure_analysis,
    type="deck",
    criterion_description=prompt,
    agent_prompt_template=prompt,
    task_prompt_template=BASE_DECK_TASK_PROMPT,
    pydantic=DeckStructureAnalysis,
    applicable_slide_types=None,  # Applies to entire deck
    priority=1,
    requires_slide_type=True,  # Needs slide types to evaluate structure
    category="structure"
)

