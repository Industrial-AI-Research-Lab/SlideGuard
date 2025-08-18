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
- Some elements may be combined into one slide, which is not a problem in general, but for slide deck clarity it is better to have them separated

## Evaluation Guidelines:
- Point to the exact slides / elements where the issue is observed
- Provide specific, actionable suggestions that are as concrete as possible
- Focus on structure principles (presence of all the key structural elements in the correct order)
- Only report issues you are confident about

## Response Format:
Your response should have two sections: Thought and Answer.
In the Thought section, provide your reasoning and analysis including an overall assessment of the deck structure.
In the Answer section, provide the final evaluation in JSON format with specific issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.

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

