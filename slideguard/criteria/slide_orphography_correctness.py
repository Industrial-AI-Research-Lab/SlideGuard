from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """You are an expert in working with students' presentations.
You will be provided with a screenshot of a presentation slide.
Your task is to check whether the slide has any orthographic or grammatical errors.

What can be considered as an error:
- spelling errors
- punctuation errors, including ending dots in titles or lists
- capitalization errors
- grammatical errors

The plan of the solution of the task:
1. Review the entire slide of the presentation and find typographical and grammatical errors.
2. When checking grammar and punctuation make sure that you consider the whole element, not just a part of it (some elements may occupy several lines, so you need to check the whole element).
3. Formulate conclusions about how to correct each error found on the slide.

Common problems that can be found on a slide:
- Lists may have ending dots which is not correct

Your answer should have two sections: «Thought» and «Answer».

First, in the «Thought:» section, write down your reasoning on the task strictly in accordance with the plan of the solution of the task. Perform all the steps of the plan of the solution of the task and describe your results.
Then, in the «Answer:» section, write the final answer for the user in Russian, based on your reasoning, namely list all the problems you found, if there are any.

Strictly follow the following rules:
- usually in presentations there are very few orthographic and grammatical errors, so make sure you are sure you have found them
- always provide the «Thought:» section, and the «Answer:» section, otherwise you will not be able to complete the task
- in the «Answer:» section, provide only a description of the problems in the form of clear comments for the user on the errors that need to be corrected, if you have no comments on the task, write only 'Problems not found' and nothing else

Write the final answer in the following JSON format:
{schema_format}
"""

class SlideOrphographyCorrectnessResult(BaseAttributes):
    evaluation_element: str = Field(description="Orphographic error")
    evaluation_suggestion: str = Field(description="Fix the word <<incorrect word>>")

class SlideOrphographyCorrectness(BaseModel):
    evaluation_results: list[SlideOrphographyCorrectnessResult] = Field(description="List of identified content issues")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)

SLIDE_ORPHOGRAPHY_CORRECTNESS = CriterionInfo(
    criteria=Criteria.slide_orphography_correctness,
    type="slide",
    criterion_description="Analyzing whether the slide has any typographical or grammatical errors and provide appropriate suggestions",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_SLIDE_TASK_PROMPT,
    pydantic=SlideOrphographyCorrectness,
    applicable_slide_types=None,
    priority=4,
    requires_slide_type=False,
    category="visual"
)