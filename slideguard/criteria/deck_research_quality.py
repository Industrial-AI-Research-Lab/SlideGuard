from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_DECK_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in evaluating the research quality of students' presentations.
You will be provided with information about all slides in the presentation.

Your task is to assess whether the presentation demonstrates a strong research foundation by carefully analyzing the content slide by slide.

## Core Research Requirements:
- Evidence-based approach to problem solving
- It is clearly obvious what was proposed by the student and how it improves the current state
- The research is conducted in a scientific way - correct use of scientific terms and concepts, correct methods and metrics
- Experimental design (sample size, control groups, metrics, datasets) is adequate and justified
- Statistical or analytical techniques are used appropriately (e.g., significance testing, error margins)
- Are the experiments, datasets, or analyses adequate in number and depth for the research question?
- Future research directions (if available) are suggested and logically flow from the findings

## Common Problems to Identify:
- Abscence of a slide with overall proposed approach / method / solution that can ease the understanding of what exactly was done
- Not enough experiments to support the proposed solution
- A lot of important research details are missing

## What is not a problem:
- It is fine when not all the fine-grained details of the experiments are covered, but the overall approach is clear

## Evaluation Guidelines:
- Always point to the exact slide where the issue or strength is observed
- Provide specific, actionable suggestions (e.g., “On Slide 5, the methodology is vague; specify the sample size and justify why it is sufficient”)
- Provide concrete examples and suggestions for improvement
- Focus on research design principles (evidence-based approach, clarity of the proposed solution, scientific rigor)
- Only report issues you are confident about

## Response Format:
Your answer must contain two sections: "Thought" and "Answer".
Evaluate the presentation's research quality by examining the evidence-based approach to problem solving, the clarity of the proposed solution, and the scientific rigor of the research.
Provide specific suggestions for improving the research quality of the presentation.

The answer in the 'Answer' section should be in the following JSON format:
{schema_format}
"""


class DeckResearchQualityResult(BaseAttributes):
    evaluation_element: str = Field(description="Evaluation element")
    evaluation_suggestion: str = Field(description="Evaluation suggestion")


class DeckResearchQuality(BaseModel):
    evaluation_results: list[DeckResearchQualityResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


DECK_RESEARCH_QUALITY = CriterionInfo(
    criteria=Criteria.deck_research_quality,
    type="deck",
    criterion_description="Evaluating the research quality of students' presentations",
    agent_prompt_template=prompt,
    task_prompt_template=BASE_DECK_TASK_PROMPT,
    pydantic=DeckResearchQuality,
    applicable_slide_types=None,  # Applies to all slide types
    priority=3,
    requires_slide_type=False,
    category="research"
)

