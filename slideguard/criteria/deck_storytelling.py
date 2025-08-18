from pydantic import BaseModel, Field
from slideguard.criteria.base import BASE_DECK_TASK_PROMPT, BaseAttributes, CriterionInfo
from slideguard.schemes import Criteria

prompt = """
You are an expert in evaluating the storytelling quality of students' presentations.
You will be provided with information about all slides in the presentation.

Your task is to assess whether the presentation tells a coherent, logical story by evaluating:

## Key Storytelling Elements to Evaluate:
- Logical progression from introduction to conclusion
- Clear cause-and-effect relationships between ideas
- Smooth transitions between related topics
- Proper topic separation when switching between different topics
- Each slide should be a part of coherent overall story 
- No contradictions or conflicting information
- The title of the whole presentation should be a good reflection of the content of the presentation

## Evaluation Plan:
Evaluate the presentation's storytelling quality by examining the logical connections between slides according to the Required Logical Connections (Mermaid Diagram):
```mermaid
graph LR
A[Motivation] <--> B[Goal]
A[Motivation] --> C[Proposed Solution]
C[Proposed Solution] --> F[Experiment Settings]
A[Motivation] <--> E[Current State]
E[Current State] --> B[Goal]
B[Goal] --> D[Tasks]
B[Goal] <--> C[Proposed Solution]
D[Tasks] --> F[Experiment Settings]
F[Experiment Settings] --> G[Experiment Results]
A[Motivation] --> G[Experiment Results]
```

## Evaluation Criteria:
1. **Motivation → Goal Connection**: Does the goal address the motivation/problem?
2. **Current State → Goal Connection**: Does the goal propose improvement over current state?
3. **Goal → Tasks Connection**: Do tasks directly support achieving the goal?
4. **Goal → Solution Connection**: Does the proposed solution align with the goal?
5. **Solution → Experiments Connection**: Do experiments test the proposed solution and provide explicit result that this approach is better than the current state in some way?
6. **Experiments → Results Connection**: Do results relate to the experimental setup?
7. **Motivation → Results Connection**: Do results address the original motivation?

## Common Problems to Identify:
- If Goal does not mention improvement of Current State → violation
- If Tasks do not refer to a specific Goal → violation
- If Proposed Solution doesn't address the stated Goal → violation
- If Experiment Settings don't test the Proposed Solution → violation
- If Experiment Results don't connect back to the original Motivation → violation
- If some slide is not a part of the overall story → violation
- If the title of the whole presentation is not a good reflection of the content of the presentation → violation

## Evaluation Guidelines:
- Point to the exact slides / elements where the issue is observed
- Provide specific, actionable suggestions that are as concrete as possible
- Focus on storytelling principles (logical flow, cause-and-effect relationships, smooth transitions, proper topic separation, coherence of the story)
- Only report issues you are confident about

## Response Format:
Your response should have two sections: Thought and Answer.
In the Thought section, provide your reasoning and analysis including an overall assessment of the deck storytelling.
In the Answer section, provide the final evaluation in JSON format with specific issues identified, concrete suggestions for improvement, and an overall score from 1 to 5.

The answer in the 'Answer' section should be in the following JSON format:
{schema_format}
"""


class DeckStorytellingResult(BaseAttributes):
    evaluation_element: str = Field(description="Issue description")
    evaluation_suggestion: str = Field(description="Detailed description of the issue and suggestion for improvement")


class DeckStorytelling(BaseModel):
    evaluation_results: list[DeckStorytellingResult] = Field(description="List of evaluation results with specific elements and suggestions")
    score: int = Field(description="Score from 1 to 5. If no issues found, always give 5")


DECK_STORYTELLING = CriterionInfo(
    criteria=Criteria.deck_storytelling,
    type="deck",
    criterion_description='You are an expert in evaluating the storytelling quality of students\' presentations. Your task is to assess whether the presentation tells a coherent, logical story by evaluating: Logical progression from introduction to conclusion, Clear cause-and-effect relationships between ideas, Smooth transitions between related topics, Proper topic separation when switching between unrelated subjects, No contradictions or conflicting information',
    agent_prompt_template=prompt,
    task_prompt_template=BASE_DECK_TASK_PROMPT,
    pydantic=DeckStorytelling,
    applicable_slide_types=None,  # Applies to entire deck
    priority=1,
    requires_slide_type=True,  # Needs slide types to evaluate structure
    category="structure"
)

