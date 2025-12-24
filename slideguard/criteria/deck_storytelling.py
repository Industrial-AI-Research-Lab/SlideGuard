from typing import Optional
from slideguard.criteria.presentation_types import PresentationType


def generate_prompt(presentation_type: Optional[PresentationType] = None) -> str:
    """
    Generate storytelling quality evaluation prompt based on presentation type.
    
    Args:
        presentation_type: The type of presentation, or None for default prompt
        
    Returns:
        Prompt string tailored to the presentation type
    """
    base_prompt = """
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
{presentation_type_specific_content}

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
In the Answer section, provide the final evaluation strictly following the format instructions.
"""
    
    # Define presentation type specific content
    type_specific_content = {
        PresentationType.SCIENTIFIC: """
8. **Current State → Scientific Novelty Connection**: Does literature review justify claimed scientific novelty?
""",
        PresentationType.INDUSTRIAL: """
8. **Industrial Potential → Experimental Results Connection**: Do results demonstrate practical industrial applicability?
""",
        PresentationType.COLLABORATIVE: """
8. **Collaborative Progress → Experimental Results Connection**: Does team communication progress lead to collaborative outcomes?
""",
        PresentationType.TECHNOLOGICAL: """
8. **Current State → Technological Novelty Connection**: Does similar solutions review justify claimed technological novelty?
""",
    }
    
    # Get specific content for the presentation type, or empty string if None
    specific_content = type_specific_content.get(presentation_type, "")
    
    # Format the prompt with the specific content
    return base_prompt.format(presentation_type_specific_content=specific_content)


# Default prompt for backward compatibility
prompt = generate_prompt()
