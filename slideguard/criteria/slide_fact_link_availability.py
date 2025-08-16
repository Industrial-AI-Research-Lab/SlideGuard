from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, CriterionInfo
from slideguard.schemes import Criteria

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide. 
Your task is to check whether the numerical data (including data presented in the form of diagrams, graphs, tables) on the slide is justified and whether links to sources are provided.
Do not pay attention to any other data, except numerical data.
Fix if the link is missing, invalid, or the data is unjustified.

Your answer should have two sections: Thought and Answer.

First, in the 'Thought' section, write down your reasoning on the task, including searching for links and facts that must be supported by sources on the slide. Make sure that important information on the slide is provided with links to sources. The link is usually at the bottom of the slide and can represent a URL, the name of a book or article, or have an explanatory word "source" or something similar. Very carefully check that you did not miss mentioning the source on the slide, otherwise you will get a penalty.
Then, in the 'Answer' section: write the final answer for the user in Russian, namely list all the problems, if there are any.

Strictly follow the following rules:
- **very carefully** check the slide for the presence of sources of information, explicitly write in the 'Thought' section of the reasoning on the task which sources you found
- determine if there are any pictures of infographics on the slide that represent numerical or financial data
- for each such picture of infographics, make sure that the infographic represents data that is external to the operational activity of the company whose slide we are considering. If the infographic picture represents data that belongs to the company itself (for example, the number of product sales or the loading of company warehouses), then skip this infographic and do not check it further.
- always provide the 'Thought:' section, and the 'Answer:' section, otherwise you will not be able to complete the task
- in the 'Answer:' section, provide only clear comments for the user on the presence of sources, if they were required on the slide
- if you have no comments on the slide in the 'Answer:' section, write **only** 'Problems not found' and nothing else

Write the result in a JSON format.
"""


class SlideFactLinkAvailabilityResult(BaseModel):
    evaluation_element: str = Field(description="Comment on the slide ")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")


class SlideFactLinkAvailability(BaseModel):
    evaluation_results: list[SlideFactLinkAvailabilityResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


SLIDE_FACT_LINK_AVAILABILITY = CriterionInfo(
    criteria=Criteria.slide_fact_link_availability,
    type="slide",
    criterion_description="Analyzing whether fact links are available on the slide and provide appropriate suggestions",
    agent_prompt=prompt,
    task_prompt=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideFactLinkAvailability,
    applicable_slide_types=["current_state", "proposed_solution", "experimental_results"],
    priority=4,
    requires_slide_type=True,
    category="visual"
)

