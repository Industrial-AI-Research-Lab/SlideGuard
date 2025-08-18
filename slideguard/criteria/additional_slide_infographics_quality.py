from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide. 
Your task is to analyze the slide and determine if the infographics on the slide are of good quality and correctly present the intended information.

## Key Visual Elements to Evaluate:
- infographics on the slide which are not background images

## Common Problems to Identify:
- 

## What is not a problem:
- 

## Evaluation Guidelines:
- 

## Response Format:
Your answer should have two sections: Thought and Answer.
First, in the 'Thought' section, write down your reasoning on the task, including an analysis of the slide content, whether there is a visualization on the slide, and how the visualization corresponds to the text content. Make sure you correctly identify the visualizations on the slide, for example, a slide may show a demonstration of a device screen, then the visualization will be the screen itself.
In the Answer section, provide the final evaluation in JSON format with specific visual issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.

The answer in the 'Answer' section should be in the following JSON format:
{schema_format}
"""

class SlideGraphicContentMatchResult(BaseAttributes):
    evaluation_element: str = Field(description="Comment on the slide issue")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")

class SlideGraphicContentMatch(BaseModel):
    evaluation_results: list[SlideGraphicContentMatchResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


SLIDE_GRAPHIC_CONTENT_MATCH = CriterionInfo(
    criteria=Criteria.slide_graphic_content_match,
    type="slide",
    criterion_description="Analyzing whether graphic content matches the slide content and provide appropriate suggestions",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideGraphicContentMatch,
    applicable_slide_types=["experiment_settings", "experimental_results"],
    priority=4,
    requires_slide_type=True,
    category="visual"
)