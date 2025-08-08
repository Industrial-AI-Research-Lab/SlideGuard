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

class ColorIssue(BaseModel):
    issue_type: str = Field(description="Type of color issue (contrast, harmony, accessibility, etc.)")
    description: str = Field(description="Detailed description of the issue")
    impact: str = Field(description="Impact on audience understanding or engagement")
    suggestion: str = Field(description="Specific suggestion for improvement")
    alternative_colors: list[str] = Field(description="Alternative color recommendations")

class SlideColorAnalysis(BaseModel):
    color_issues: list[ColorIssue] = Field(description="List of identified color issues")
    overall_color_score: int = Field(description="Overall color score from 1 to 5", ge=1, le=5)
    color_harmony_score: int = Field(description="Color harmony score from 1 to 5", ge=1, le=5)
    accessibility_score: int = Field(description="Accessibility score from 1 to 5", ge=1, le=5)
    recommendations: list[str] = Field(description="List of specific recommendations")

slide_color_analysis = CriterionInfo(
    criterion_name="Slide Color Analysis",
    criterion_type="slide",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=SlideColorAnalysis,
    # This criterion is most relevant for slides with visual content
    applicable_slide_types=["motivation", "goals", "current_state", "proposed_solution", "experimental_results"],
    priority=3,
    requires_slide_type=True,  # Needs to know slide type to provide context-appropriate advice
    category="visual"
)
