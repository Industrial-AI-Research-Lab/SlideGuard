from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in visual presentation design.
You will be provided with a screenshot of a presentation.
Your task is to check whether the color scheme and fonts correspond to the general style (one group of fonts, no more than 5 colors).

**IMPORTANT!** Do not comment on the slide content or business recommendations. Avoid your own comments.

Write the result in the following JSON format:
{schema_format}
"""


class SlideColorAndFontsAnalysisResult(BaseModel):
    evaluation_element: str = Field(description="Comment on the slide ")
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
    applicable_slide_types=["Title slide", "Motivation", "Goal", "Current State", "Proposed Solution", "Experimental Results", "Conclusion"],
    priority=4,
    requires_slide_type=False,  # Can evaluate without knowing slide type
    category="visual"
)

