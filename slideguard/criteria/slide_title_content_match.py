from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide.
Your task is to analyze the slide and determine if the title matches the content of the slide.

## Evaluation Plan:
1. VERY VERY carefully look at the provided screenshot and write down the title if it is present
2. Formulate the main idea of the slide content without considering the title
3. Compare the title and the main idea of the slide content
4. Draw a conclusion about the correspondence between the title and slide content
5. Describe specifically what the mismatch consists of from the title's side
6. If there is a mismatch, suggest how this mismatch could be corrected by changing the title

## What is not a problem:
- Slide which is connected to goal and tasks may have simple naming like "Goal and Tasks"

## Evaluation Guidelines:
- if the slide is NOT a title slide or separator slide, then it must have a title; if there is no title, make a note about it
- ensure that the slide title corresponds to its content; the title should accurately reflect the main idea of the slide, making it understandable even without further study of the text or infographics on the slide. If you see a mismatch, make a note and describe specifically what this mismatch consists of
- the title should not have too broad a scope; it should be specific and precise, reflecting the main idea of the slide
- the title should not be abstract; it should be specific and precise, reflecting the main idea of the slide
- if you think the title does not match the slide content, be sure to suggest your own title

## Response Format:
Your response should have two sections: Thought and Answer.
First, in the 'Thought' section, provide your reasoning on the task STRICTLY following the problem-solving plan and marking individual stages of the task solution.
Then in the 'Answer' section, rewrite the found mismatches and how to fix them, if any, in the form of a final answer in the following JSON format:
{schema_format}
"""

class SlideTitleContentMatchResult(BaseAttributes):
    evaluation_element: str = Field(description="Comment on the slide issue")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")

class SlideTitleContentMatch(BaseModel):
    evaluation_results: list[SlideTitleContentMatchResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

SLIDE_TITLE_CONTENT_MATCH = CriterionInfo(
    criteria=Criteria.slide_title_content_match,
    type="slide",
    criterion_description="Analyzing whether slide titles match their content and provide appropriate suggestions",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideTitleContentMatch,
    applicable_slide_types=None,  # Applies to all slide types
    priority=3,
    requires_slide_type=False,
    category="visual"
)