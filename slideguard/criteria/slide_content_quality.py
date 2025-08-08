from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo

prompt = """
You are an expert in content quality assessment for presentations.
You will be provided with a screenshot of one slide from a presentation.
Your task is to evaluate the content quality, clarity, and effectiveness of the slide.

Focus on the following aspects:
1. Content clarity and comprehensibility
2. Information density and balance
3. Logical flow and organization
4. Use of appropriate visual aids
5. Audience appropriateness
6. Technical accuracy (if applicable)

For each issue identified, provide:
- Specific description of the problem
- Impact on audience understanding
- Concrete suggestions for improvement
- Best practices recommendations

Your response should be in JSON format:
{schema_format}
"""

class ContentIssue(BaseModel):
    issue_type: str = Field(description="Type of content issue (clarity, density, flow, etc.)")
    description: str = Field(description="Detailed description of the issue")
    impact: str = Field(description="Impact on audience understanding")
    suggestion: str = Field(description="Specific suggestion for improvement")
    best_practice: str = Field(description="Relevant best practice recommendation")

class SlideContentQuality(BaseModel):
    content_issues: list[ContentIssue] = Field(description="List of identified content issues")
    clarity_score: int = Field(description="Content clarity score from 1 to 5", ge=1, le=5)
    organization_score: int = Field(description="Content organization score from 1 to 5", ge=1, le=5)
    effectiveness_score: int = Field(description="Overall effectiveness score from 1 to 5", ge=1, le=5)
    recommendations: list[str] = Field(description="List of specific recommendations")

slide_content_quality = CriterionInfo(
    criterion_name="Slide Content Quality",
    criterion_type="slide",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=SlideContentQuality,
    # This criterion is most relevant for content-heavy slides
    applicable_slide_types=["goals", "tasks", "current_state", "proposed_solution", "experiment_settings", "experimental_results", "conclusion"],
    priority=2,
    requires_slide_type=True,  # Needs to know slide type to provide context-appropriate advice
    category="content"
) 