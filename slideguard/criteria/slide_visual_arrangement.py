from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in slide visual design and readability analysis.
You will be provided with a screenshot of one slide from a presentation.
Your task is to evaluate the visual arrangement, layout, and readability of elements on the slide. Focus specifically on how the visual design affects information perception and audience comprehension.

## Key Visual Arrangement Elements to Evaluate:
- Text readability (only focus on the size of the text)
- Layout organization (alignment, spacing, hierarchy)
- Information density (how much information is on the slide)

## Common Problems to Identify:
- Text that is too small for easy reading
- Cluttered layout with insufficient spacing between elements
- Some text elements can be on top of other elements, which makes it difficult to read
- Overcrowded slides with too much information
- Poor visual hierarchy or inconsistent formatting

## What is not a problem:
- It is fine when elements are not aligned to the center of the slide
- Numbered lists instead of bullet points
- Slide title size can be larger than the rest of the text and it is not a problem

## Evaluation Guidelines:
- Be specific about what needs to be changed and where on the slide
- Provide concrete examples and suggestions for improvement
- Focus on visual design principles (contrast, alignment, proximity, repetition)
- Only report issues you are confident about

## Response Format:
Your response should have two sections: Thought and Answer.
In the Thought section, provide your reasoning and analysis including an overall visual assessment of the slide, identification of the slide title and its visual treatment, and analysis of layout structure and information hierarchy.
In the Answer section, provide the final evaluation in JSON format with specific visual issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.

The answer in the 'Answer' section should be in the following JSON format:
{schema_format}
"""

class SlideVisualArrangementResult(BaseAttributes):
    evaluation_element: str = Field(description="Comment on the slide issue")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")

class SlideVisualArrangement(BaseModel):
    evaluation_results: list[SlideVisualArrangementResult] = Field(description="List of identified visual issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


SLIDE_VISUAL_ARRANGEMENT = CriterionInfo(
    criteria=Criteria.slide_visual_arrangement,
    type="slide",
    criterion_description="Visual arrangement of the slide",
    agent_prompt_template=prompt.format(schema_format=SlideVisualArrangement.model_json_schema()),
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideVisualArrangement,
    applicable_slide_types=None,  # Applies to all slide types
    priority=2,
    requires_slide_type=False,
    category="visual"
)
