from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, CriterionInfo
from slideguard.schemes import Criteria
from slideguard.schemes import SlideType
from slideguard.criteria.slide_types import generate_slide_helper_type_prompt

# Generate prompt dynamically from slide type manager
prompt = generate_slide_helper_type_prompt()

prompt = """
You are an expert in detailed presentation analysis. You are provided with a single slide.
You need to describe it in maximum detail so that the information can be used to evaluate the structure of the entire presentation.
DO NOT make assumptions and DO NOT invent anything regarding what might be on other slides.
You always work with only one slide.

You need to remember that slides can contain information of the following types and also belong to the corresponding sections:
1) Title slide - this is the first slide of the presentation. It usually contains the title of the presentation and the name of the presenter and scientific advisor.

2) Separator - this is a slide that separates logical sections of the presentation. Usually contains only a title or title and illustration.

3) Motivation - this is a slide that contains information about the motivation for the project.

4) Current State - this is a slide that contains information about the current state of the field and existing products / methods / solutions.

5) Goal - slide that contain information about goals that need to be achieved to implement the project or product, which is the subject of the entire presentation.
Goals must be EXPLICITLY FORMULATED. Remember that goals can only be statements (including those transmitted through infographic) ALWAYS directed into the future.
Information about past results, achievements, experience, about what has already been done, CANNOT be a goal.

6) Tasks - slide that contain information about tasks that need to be performed to implement the project or product, which is the subject of the entire presentation.
Differ from goals in that they describe actions, not the final state to which you need to go.

7) Proposed Solution - this is a slide that contains information about the proposed solution to the problem. Can be shown as a workflow or a diagram with description.

8) Experiment Settings - slide with description of used for experiments datasets or description of hyperparameters of used methods and models  .

9) Experimental Results - this is a slide that contains information about the experimental results that show the effectiveness of the proposed solution.

10) Conclusion - this is a slide that contains information about the conclusion of the presentation.

IMPORTANT! You cannot specify more than three types for one slide. But you can not specify any type if the slide does not belong to any of the listed types.
"""


SLIDE_HELPER_TYPE = CriterionInfo(
    criteria=Criteria.slide_type,
    type="slide",
    criterion_description="Type of the slide",
    agent_prompt=prompt,
    task_prompt=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideType,
    applicable_slide_types=None,  # Applies to all slide types
    priority=1,  # High priority - needed by other criteria
    requires_slide_type=False,
    category="structure"
)