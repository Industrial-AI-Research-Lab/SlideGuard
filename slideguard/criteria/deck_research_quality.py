from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_DECK_TASK_PROMPT, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in evaluating the research quality of students' presentations.
You will be provided with information about all slides in the presentation.

Your task is to assess whether the presentation has a strong research foundation by evaluating:

**Core Research Requirements:**
- Evidence-based approach to problem solving
- It is clearly obvious what was proposed by the student and how it improves the current state
- The research is conducted in a scientific way - correct use of scientific terms and concepts, correct methods and metrics

**Response Format:**
Your answer must contain two sections: "Thought" and "Answer".

**Thought Section:**
Evaluate the presentation's research quality by examining the evidence-based approach to problem solving, the clarity of the proposed solution, and the scientific rigor of the research.

**Answer Section:**
Provide specific suggestions for improving the research quality of the presentation.

The answer in the 'Answer' section should be in JSON format.
"""


class DeckResearchQualityResult(BaseModel):
    evaluation_element: str = Field(description="Evaluation element")
    evaluation_suggestion: str = Field(description="Evaluation suggestion")


class DeckResearchQuality(BaseModel):
    evaluation_results: list[DeckResearchQualityResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5", ge=1, le=5)


DECK_RESEARCH_QUALITY = CriterionInfo(
    criteria=Criteria.deck_research_quality,
    type="deck",
    criterion_description="Evaluating the research quality of students' presentations",
    agent_prompt=prompt,
    task_prompt=BASE_DECK_TASK_PROMPT,
    pydantic=DeckResearchQuality,
    applicable_slide_types=None,  # Applies to all slide types
    priority=3,
    requires_slide_type=False,
    category="research"
)

