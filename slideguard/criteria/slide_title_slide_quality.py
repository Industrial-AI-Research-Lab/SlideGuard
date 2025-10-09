from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria
from slideguard.criteria.slide_types import SlideType

prompt = """You are an expert in analyzing student presentations.
You will be provided with a screenshot of the title slide of a presentation.
On it, you need to check the presence of the following elements:
- Name (or logo) of the university
- Title of the presentation
- Last name, first name and group of the student
- Last name, first name and place of work of the supervisor
- Place (city) and year of the presentation

If some of the elements are missing, then you need to make a remark and suggest to fix it.

## Evaluation Guidelines:
- Be specific about what needs to be changed and where on the slide
- Provide concrete examples and suggestions for improvement
- Focus on the presence of all the key elements
- Only report issues you are confident about
- When setting overall score - 1 is the strict violation, 5 is the best score

## Response Format:
Your answer should have two sections: «Thought» and «Answer».
In the Thought section, provide your reasoning and analysis including an overall assessment of the slide title.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.
"""

class SlideTitleSlideQualityResult(BaseAttributes):
    evaluation_element: str = Field(description="Comment on the slide issue")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")

class SlideTitleSlideQuality(BaseModel):
    evaluation_results: list[SlideTitleSlideQualityResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

SLIDE_TITLE_SLIDE_QUALITY = CriterionInfo(
    criteria=Criteria.slide_title_slide_quality,
    type="slide",
    criterion_description="Analyzing whether the slide title matches the slide quality",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideTitleSlideQuality,
    applicable_slide_types=[SlideType.TITLE_SLIDE.value],
    priority=4,
    requires_slide_type=True,
    category="visual"
)