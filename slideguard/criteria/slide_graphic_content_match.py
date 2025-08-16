from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, CriterionInfo
from slideguard.schemes import Criteria

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide that may contain a visualization. 
Your task is to analyze the slide and determine if the textual elements of the slide correspond to numerical graphics (e.g., boxplots, circular and bar charts, graphs, tables with data). 
If the visualization is not numerical, then it should be ignored and not checked for consistency with the text content.
Any other infographics (e.g., a diagram, picture, illustration) are not considered numerical visualizations and are not checked for consistency with the text content.

Your answer should have two sections: Thought and Answer.

First, in the 'Thought' section, write down your reasoning on the task, including an analysis of the slide content, whether there is a visualization on the slide, and how the visualization corresponds to the text content. Make sure you correctly identify the visualizations on the slide, for example, a slide may show a demonstration of a device screen, then the visualization will be the screen itself.
Then, in the 'Answer' section: write the final answer for the user in Russian, namely list all the problems, if there are any.

Strictly follow the following rules:
- determine which idea on the slide is illustrated by the visualization, how it corresponds to the text content of the slide, if it does not correspond, write in what exactly the problem is
- always provide the 'Thought:' section, and the 'Answer:' section, otherwise you will not be able to complete the task
- in the 'Answer:' section, provide only clear comments for the user on the consistency of the infographic with the slide content, if you have no comments on the slide, write **only** 'Problems not found' and nothing else

Write the result in a JSON format.
"""

class SlideGraphicContentMatchResult(BaseModel):
    evaluation_element: str = Field(description="Comment on the slide ")
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