from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in working with presentations.
You will be provided with a screenshot of a presentation slide.
Your task is to analyze the slide and determine if there are any abbreviations for which there is no explicit explanation.
The surrounding text of the abbreviation itself cannot be considered an explanation. The explanation must be explicit.

IMPORTANT! ONLY USE INFORMATION FROM THE IMAGE.

## The plan of the solution:
1. Search for abbreviations - carefully analyze the slide and find all abbreviations. 
Normal words and abbreviations from known words cannot be abbreviations.
2. Check for abbreviations - for each found abbreviation, check if there is an explicit explanation on the same slide.
3. Unabbreviated abbreviations - write down all abbreviations that do not have an explicit explanation on the same slide. 

## What is not a problem:
- Abbreviations which are provided on some image-screenshots (like a screenshot of a device screen or from the website or book scan) on the slide are not a problem

## Response Format:
Your answer should have two sections: Thought and Answer.
First, in the 'Thought' section, write down your reasoning on the task STRICTLY following the plan of the solution and mark the individual stages of the solution. 
Then, in the 'Answer' section, form the final answer in the following JSON format:
{schema_format}
"""


class SlideAbbreviationsResult(BaseAttributes):
    evaluation_element: str = Field(description="Found abbreviation (write here ONLY the abbreviation exactly as it appeared in the text, and nothing else)")
    evaluation_suggestion: str = Field(description="<Specify that it needs to be explained>")


class SlideAbbreviations(BaseModel):
    evaluation_results: list[SlideAbbreviationsResult] = Field(description="List of identified abbreviations")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


SLIDE_ABBREVIATIONS = CriterionInfo(
    criteria=Criteria.slide_abbreviations,
    type="slide",
    criterion_description="You are an expert in working with presentations. You will be provided with a screenshot of a presentation slide. Your task is to analyze the slide and determine if there are any abbreviations for which there is no explicit explanation. The surrounding text of the abbreviation itself cannot be considered an explanation. The explanation must be explicit.",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideAbbreviations,
    # This criterion is most relevant for slides with visual content
    applicable_slide_types=None,
    priority=4,
    requires_slide_type=False,  # Can evaluate without knowing slide type
    category="visual"
)