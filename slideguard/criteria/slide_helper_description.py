from pydantic import BaseModel, Field
from slideguard.criteria.base import CriterionInfo

prompt = """
You are an expert in detailed presentation analysis. You are provided with ONLY ONE single slide.
You need to describe it in maximum detail so that the information can be used to evaluate the structure of the entire presentation.
DO NOT make assumptions and DO NOT invent anything regarding what might be on other slides.
You always work with only one slide.

Describe the slide according to the following plan:
1. **Story**
    - first compose a story based only on the slide given to you
2. For each infographic or chart on the slide, describe the data it shows and make a conclusion about what conclusion the reader can draw by looking at it.

**IMPORTANT:**
- Give ONLY detailed description — without analysis and conclusions.
- Structure the answer clearly and completely.
"""

class SlideDescription(BaseModel):
    title: str = Field(description="Exact explicit slide title. If there is no clear title at the top of the slide, output 'No title' here")
    description: str = Field(description="Detailed description of the slide, including description of all charts, tables and illustrations and how they are arranged")
    summary: str = Field(description="Brief but comprehensive description of this individual slide")

slide_helper_description = CriterionInfo(
    criterion_name="Slide Description",
    criterion_type="slide",
    criterion_description="You are an expert in detailed presentation analysis. You are provided with ONLY ONE single slide. You need to describe it in maximum detail so that the information can be used to evaluate the structure of the entire presentation. DO NOT make assumptions and DO NOT invent anything regarding what might be on other slides. You always work with only one slide.",
    criterion_prompt=prompt,
    criterion_schema=SlideDescription,
    applicable_slide_types=None,  # Applies to all slide types
    priority=1,  # Highest priority - needed by other criteria
    requires_slide_type=False,
    category="content"
)