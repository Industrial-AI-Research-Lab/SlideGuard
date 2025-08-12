from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo

prompt = """
You are an expert in color theory and visual design for presentations.
You will be provided with a screenshot of one slide from a presentation.
Your task is to evaluate the color usage and provide recommendations for improvement.

Focus on the following aspects:
1. Color contrast and readability
2. Color harmony and consistency
3. Accessibility considerations (color blindness)
4. Brand consistency (if applicable)
5. Emotional impact of color choices

For each issue identified, provide:
- Specific description of the problem
- Impact on audience understanding
- Concrete suggestions for improvement
- Alternative color recommendations

Your response should be in JSON format:
{schema_format}
"""

class SlideColorAnalysisResult(BaseModel):
    evaluation_element: str = Field(description="Evaluation element")
    evaluation_suggestion: str = Field(description="Evaluation suggestion")

class SlideColorAnalysis(BaseModel):
    evaluation_results: list[SlideColorAnalysisResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

slide_color_analysis = CriterionInfo(
    criterion_name="Slide Color Analysis",
    criterion_type="slide",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=SlideColorAnalysis,
    # This criterion is most relevant for slides with visual content
    applicable_slide_types=None,
    priority=3,
    requires_slide_type=True,  # Needs to know slide type to provide context-appropriate advice
    category="visual"
)
