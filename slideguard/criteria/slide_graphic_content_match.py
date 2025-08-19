from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide that may contain a visualization. 
Your task is to analyze the slide and determine if the textual elements of the slide correspond to the visualization.

## Key Visual Elements to Evaluate:
- Numerical graphics (e.g., boxplots, circular and bar charts, graphs, tables with data),
- Diagrams, workflows, charts describing the approach / solution

## Common Problems to Identify:
- Visualization does not correspond to the text content of the slide
- Figures should not be numbered in the presentation, e.g. "Figure 1" or "Fig.1" - it is a violation of slide design principles
- It is not possible to understand the visualization from the text content
- Text may reference some parts of the visualization, but the terminology on the visualization itself can be different, that makes it difficult to understand the visualization
- When slide describe experimental results with numerical charts or tables the surrounding text should contain some numerical analysis of the results (e.g. "The results show that the proposed approach recall is 20 percent better on average compared to approach X")
- Numerical graphics axis does not have a name and measure units, e.g. "Amount of money (USD)" - it is a strict violation of chart design principles

## What is not a problem:
- Slide may contain some background images which are decorative and not a part of the slide content - they should be ignored

## Evaluation Guidelines:
- determine which idea on the slide is illustrated by the visualization, how it corresponds to the text content of the slide, if it does not correspond, write in what exactly the problem is
- Be specific about what needs to be changed and where on the slide
- Provide concrete examples and suggestions for improvement
- Do evaluation ONLY when there is element from Key Visual Elements to Evaluate on the slide in other case no evaluation is needed
- Focus on a match between the visualization and the text content
- Only report issues you are confident about


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