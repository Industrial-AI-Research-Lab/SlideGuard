from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo

prompt = """
You are an expert in slide readability analysis.
You will be provided with a screenshot of one slide from a presentation.
Your task is to check whether the arrangement, size, and quantity of elements interfere with perception. Note that you are evaluating only the visual criterion and your comments should be related only to it.

Problems you may encounter and report to the user:
- Text on the slide may be too small to be easily readable
- There may be poor use of color, for example white text on a gray background, making text difficult to read

Follow these rules:
- Tell the user specifically what needs to be changed on the slide so they understand exactly what your comment refers to.
- If elements are arranged in a way that makes reading or information perception difficult, record this.
- Only report problems you are confident about
- Each of your comments should be accompanied by examples, i.e., contain 'for example'

Your response should have two sections: Thought and Answer.

First, in the 'Thought' section, provide your reasoning on the task, including analysis of slide content and thoughts on its correspondence to the title. Make sure you have correctly identified the slide title.
Then in the 'Answer' section: write the final answer, namely list all inconsistencies and problems if they exist. The final answer should not contain comments that do NOT have a conclusion about what needs to be fixed.
The answer in the 'Answer' section should be in JSON format:
{schema_format}
"""

class SlideVisualArrangementAnalysis(BaseModel):
    evaluation_results: list = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

slide_visual_arrangement = CriterionInfo(
    criterion_name="Slide Visual Arrangement",
    criterion_type="slide",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=SlideVisualArrangementAnalysis,
    applicable_slide_types=None,  # Applies to all slide types
    priority=2,
    requires_slide_type=False,
    category="visual"
)
