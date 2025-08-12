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

class SlideContentQualityResult(BaseModel):
    evaluation_element: str = Field(description="Comment on the slide ")
    evaluation_suggestion: str = Field(description="Suggestion for the slide")

class SlideContentQuality(BaseModel):
    evaluation_results: list[SlideContentQualityResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

slide_content_quality = CriterionInfo(
    criterion_name="Slide Content Quality",
    criterion_type="slide",
    criterion_description="You are an expert in content quality assessment for presentations. You will be provided with a screenshot of one slide from a presentation. Your task is to evaluate the content quality, clarity, and effectiveness of the slide.",
    criterion_prompt=prompt,
    criterion_schema=SlideContentQuality,
    # This criterion is most relevant for content-heavy slides
    applicable_slide_types=["Goal", "Tasks", "Current State", "Proposed Solution", "Experiment Settings", "Experimental Results", "Conclusion"],
    priority=2,
    requires_slide_type=True,  # Needs to know slide type to provide context-appropriate advice
    category="content"
) 