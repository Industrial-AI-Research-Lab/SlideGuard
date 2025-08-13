from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo

prompt = """You are an expert in analyzing student presentations.
You will be provided with a screenshot of the title slide of a presentation.
On it, you need to check the presence of the following elements:
- Name (or logo) of the university
- Name of the presentation topic
- Last name, first name and group of the student
- Last name, first name and place of work of the supervisor
- Place (city) and year of the presentation

If some of the elements are missing, then you need to make a remark and suggest to fix it.

Your answer should have two sections: «Thought» and «Answer».

First, in the «Thought:» section, write down your reasoning on the task strictly in accordance with the plan of the solution of the task. Perform all the steps of the plan of the solution of the task and describe your results.
Then, in the «Answer:» section, write the final answer for the user in Russian, based on your reasoning, namely list all the problems you found, if there are any.

Strictly follow the following rules:
- always provide the «Thought:» section, and the «Answer:» section, otherwise you will not be able to complete the task

Write the result in the following JSON format:
{schema_format}
"""

class SlideTitleSlideQualityResult(BaseModel):
    evaluation_element: str = Field(description="Comment on the slide ")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")

class SlideTitleSlideQuality(BaseModel):
    evaluation_results: list[SlideTitleSlideQualityResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

slide_title_slide_quality = CriterionInfo(
    criterion_name="Slide Title Slide Quality",
    criterion_type="slide",
    criterion_description="Analyzing whether the slide title matches the slide quality",
    criterion_prompt=prompt,
    criterion_schema=SlideTitleSlideQuality,
    applicable_slide_types=["title_slide"],
    priority=4,
    requires_slide_type=True,
    category="visual"
)