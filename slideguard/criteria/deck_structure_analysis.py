from typing import Optional
from slideguard.criteria.presentation_types import PresentationType


def generate_prompt(presentation_type: Optional[PresentationType] = None) -> str:
    """
    Generate structure analysis evaluation prompt based on presentation type.
    
    Args:
        presentation_type: The type of presentation, or None for default prompt
        
    Returns:
        Prompt string tailored to the presentation type
    """
    base_prompt = """
You are an expert in evaluating the completeness of presentation structure.
You will be provided with information about all slides in the presentation.
Your task is to check whether the presentation contains all the key structural elements in the correct order.

## Key Structural Elements to Evaluate:
- The following elements should be present in the slide deck in the following order: {presentation_type_specific_content}

## Common Problems to Identify:
- Absence of structural elements
- Incorrect order of structural elements

## What is not a problem:
- Some presentations may have extra slides after the end slide, which is not a problem
- Some elements may be combined into one slide, which is not a problem in general, but for slide deck clarity it is better to have them separated
- Extra elements such as separators can be present in the deck which is also fine

## Evaluation Guidelines:
- Point to the exact structural elements where the issue is observed, for example, "Title slide is missing" or "Motivation is not present"
- Provide specific, actionable suggestions that are as concrete as possible
- Focus on the presence of all the key structural elements in the correct order
- Only report issues you are confident about

## Response Format:
Your response should have two sections: Thought and Answer.
In the Thought section, provide your reasoning and analysis including an overall assessment of the deck structure.
In the Answer section, provide the final evaluation strictly following the format instructions.
"""
    
    # Define presentation type specific content
    type_specific_content = {
        PresentationType.SCIENTIFIC: """
1) Title Slide , 2) Motivation, 3) Goal and Tasks, 4) Current State, 5) Proposed Solution, 6) Scientific Novelty, 7) Experiment Settings, 8) Experimental Results, 9) Conclusion, 10) Publication Readiness 11) End Slide
""",
        PresentationType.INDUSTRIAL: """
1) Title Slide , 2) Motivation, 3) Goal and Tasks, 4) Current State, 5) Proposed Solution, 6) Industrial Potential, 7) Experiment Settings, 8) Experimental Results, 9) Conclusion 10) End Slide
""",
        PresentationType.COLLABORATIVE: """
1) Title Slide , 2) Motivation, 3) Goal and Tasks, 4) Current State, 5) Proposed Solution, 6) Collaborative Progress, 7) Experiment Settings, 8) Experimental Results, 9) Conclusion 10) End Slide
""",
        PresentationType.TECHNOLOGICAL: """
1) Title Slide , 2) Motivation, 3) Goal and Tasks, 4) Current State, 5) Proposed Solution, 6) Technological Novelty, 7) Technological Realization Level, 8) Experiment Settings, 9) Experimental Results, 10) Conclusion 11) End Slide
""",
    }
    
    # Get specific content for the presentation type, or empty string if None
    specific_content = type_specific_content.get(presentation_type, "")
    
    # Format the prompt with the specific content
    return base_prompt.format(presentation_type_specific_content=specific_content)


# Default prompt for backward compatibility
prompt = generate_prompt()
