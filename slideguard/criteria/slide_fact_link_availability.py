from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria
from slideguard.criteria.slide_types import SlideType

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide. 
Your task is to check whether the numerical data (including data presented in the form of diagrams, graphs, tables) on the slide is justified and whether links to sources are provided.
Do not pay attention to any other data, except numerical data.
Fix if the link is missing, invalid, or the data is unjustified.

## Key Elements to Evaluate:
- Links to the sources for numerical data (including data presented in the form of diagrams, graphs, tables)

## Common Problems to Identify:
- Links to the sources are missing while they should be present to justify the numerical data

## What is not a problem:
- Slides may contain experimental results made by the student - this data will not have links to sources and it is not a problem

## Evaluation Guidelines:
- determine if there are any pictures of infographics on the slide that represent numerical data
- **very carefully** check the slide for the presence of sources of information, explicitly write in the 'Thought' section of the reasoning on the task which sources you found

## Response Format:
Your answer should have two sections: Thought and Answer.
First, in the 'Thought' section, write down your reasoning on the task, including searching for links and facts that must be supported by sources on the slide. Make sure that important information on the slide is provided with links to sources. The link is usually at the bottom of the slide and can represent a URL, the name of a book or article, or have an explanatory word "source" or something similar. Very carefully check that you did not miss mentioning the source on the slide, otherwise you will get a penalty.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.
"""


class SlideFactLinkAvailabilityResult(BaseAttributes):
    evaluation_element: str = Field(description="Comment on the slide issue")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")


class SlideFactLinkAvailability(BaseModel):
    evaluation_results: list[SlideFactLinkAvailabilityResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


SLIDE_FACT_LINK_AVAILABILITY = CriterionInfo(
    criteria=Criteria.slide_fact_link_availability,
    type="slide",
    criterion_description="Analyzing whether fact links are available on the slide and provide appropriate suggestions",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideFactLinkAvailability,
    applicable_slide_types=[SlideType.CURRENT_STATE.value, SlideType.PROPOSED_SOLUTION.value,
                            SlideType.EXPERIMENTAL_RESULTS.value, SlideType.EXPERIMENT_SETTINGS.value, SlideType.MOTIVATION.value],
    priority=4,
    requires_slide_type=True,
    category="visual"
)

