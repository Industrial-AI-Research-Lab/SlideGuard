from pydantic import BaseModel, Field
from slideguard.criteria_info.base import CriterionInfo

prompt = """
You are an expert in visual design and presentation analysis. You are provided with a single slide.
Analyze the visual consistency and design elements of this slide.

Evaluate the following aspects:
1. **Color Scheme**: Consistency and appropriateness of colors used
2. **Typography**: Font choices, sizes, and hierarchy
3. **Layout**: Balance, alignment, and spacing
4. **Visual Elements**: Charts, images, and graphics consistency
5. **Overall Design**: Professional appearance and visual appeal

Provide a detailed analysis focusing on visual consistency and design quality.
"""

class VisualConsistencyAnalysis(BaseModel):
    color_scheme_score: int = Field(description="Score from 1-10 for color scheme consistency", ge=1, le=10)
    typography_score: int = Field(description="Score from 1-10 for typography quality", ge=1, le=10)
    layout_score: int = Field(description="Score from 1-10 for layout and spacing", ge=1, le=10)
    visual_elements_score: int = Field(description="Score from 1-10 for visual elements consistency", ge=1, le=10)
    overall_design_score: int = Field(description="Overall design score from 1-10", ge=1, le=10)
    analysis: str = Field(description="Detailed analysis of visual consistency and design elements")
    recommendations: str = Field(description="Specific recommendations for improvement")

slide_visual_consistency = CriterionInfo(
    criterion_name="Visual Consistency",
    criterion_type="slide",
    criterion_description=prompt,
    criterion_prompt=prompt,
    criterion_schema=VisualConsistencyAnalysis
)
