from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, CriterionInfo
from slideguard.schemes import Criteria, SlideDescription

prompt = """
You are an expert in detailed presentation analysis. You are provided with ONLY ONE single slide.
You need to describe it in maximum detail so that the information can be used to evaluate the structure and coherence of the entire presentation.
DO NOT make assumptions and DO NOT invent anything regarding what might be on other slides.
You always work with only one slide.

Describe the slide in maximum detail according to the following plan:
1. Get the title of the slide - pay attention that it can be not only in the top of the slide, but also in the middle of the slide if we talk about title slide or separator slide.
2. Describe the content of the slide in maximum detail.
3. For each infographic or chart on the slide, describe the data it shows and make a conclusion about what conclusion the reader can draw by looking at it.
4. Make a good summary of the slide content.

**IMPORTANT:**
- Give ONLY detailed description — without analysis and conclusions.
- Structure the answer clearly and completely.

Return the result in JSON as instructed by the format instructions.
"""

SLIDE_HELPER_DESCRIPTION = CriterionInfo(
    criteria=Criteria.slide_description,
    criterion_description="Detailed description of the slide, including description of all charts, tables and illustrations and how they are arranged",
    type="slide",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideDescription,
    applicable_slide_types=None,  # Applies to all slide types
    priority=1,  # Highest priority - needed by other criteria
    requires_slide_type=False,
    category="content"
)
