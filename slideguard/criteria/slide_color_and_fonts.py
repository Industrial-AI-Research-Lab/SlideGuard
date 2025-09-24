from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria
from slideguard.criteria.slide_types import SlideType

prompt = """
You are an expert in visual presentation design.
You will be provided with a screenshot of a presentation.
Your task is to check whether the color scheme and fonts correspond to the general style (one group of fonts, no more than 5 colors).

## Key Visual Elements to Evaluate:
- Color usage and contrast
- Selection of fonts and their contrast
- Visual balance

## Common Problems to Identify:
- Text has poor contrast for easy reading (e.g., white text on light gray background)
- Too vivid colors, which can be distracting for the reader
- Too many fonts on the slide
- More than 5 colors on the slide

## Evaluation Guidelines:
- Be specific about what needs to be changed and where on the slide
- Provide concrete examples and suggestions for improvement
- Focus on color and fonts design principles (contrast, repetition, visual balance)
- Only report issues you are confident about

## What is not a problem:
- It is fine when there are different fonts on the slide, but they are used for different elements (e.g. images on a slide)
- If slide color scheme is generally fine and you can suggest very minor improvements do not mention them in the evaluation results, as it is not an issue

## Response Format:
Your response should have two sections: Thought and Answer.
In the Thought section, provide your reasoning and analysis including an overall assessment of the slide color scheme and fonts.
In the Answer section, provide the final evaluation in JSON format with specific visual issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.

The answer in the 'Answer' section should be in the following JSON format:
{schema_format}
"""


class SlideColorAndFontsAnalysisResult(BaseAttributes):
    evaluation_element: str = Field(description="Comment on the slide issue")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")


class SlideColorAndFontsAnalysis(BaseModel):
    evaluation_results: list[SlideColorAndFontsAnalysisResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


SLIDE_COLOR_AND_FONTS = CriterionInfo(
    criteria=Criteria.slide_color_and_fonts,
    type="slide",
    criterion_description="Checking the color scheme and fonts of the slide",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideColorAndFontsAnalysis,
    # This criterion is most relevant for slides with visual content
    applicable_slide_types=[SlideType.TITLE_SLIDE.value, SlideType.MOTIVATION.value, SlideType.GOAL.value, SlideType.CURRENT_STATE.value, SlideType.PROPOSED_SOLUTION.value, SlideType.EXPERIMENTAL_RESULTS.value, SlideType.CONCLUSION.value],
    priority=4,
    requires_slide_type=False,  # Can evaluate without knowing slide type
    category="visual"
)

