from typing import Optional
from slideguard.criteria.presentation_types import PresentationType


def generate_prompt(presentation_type: Optional[PresentationType] = None) -> str:
    """
    Generate research quality evaluation prompt based on presentation type.
    
    Args:
        presentation_type: The type of presentation, or None for default prompt
        
    Returns:
        Prompt string tailored to the presentation type
    """
    base_prompt = """
You are an expert in evaluating the research quality of students' presentations.
You will be provided with information about all slides in the presentation.

Your task is to assess whether the presentation demonstrates a strong research foundation by carefully analyzing the content slide by slide.

## Core Research Requirements:
- The goal of the research is clear and justified, there should be only one goal for the research
- Evidence-based approach to problem solving
- It is clearly obvious what was proposed by the student and how it improves the current state
- The research is conducted in a scientific way - correct use of scientific terms and concepts, correct methods and metrics
- Analysis of the current state is provided and it is clear what is the problem and how it can be solved
- Experimental design (sample size, control groups, metrics, datasets) is adequate and justified
- Statistical or analytical techniques are used appropriately (e.g., significance testing, error margins)
- Are the experiments, datasets, or analyses adequate in number and depth for the research question?
- Future research directions (if available) are suggested and logically flow from the findings
{presentation_type_specific_content}

## Common Problems to Identify:
- Abscence of a slide with overall proposed approach / method / solution that can ease the understanding of what exactly was done
- Analysis of the current state is weak - comparison criteria are strange (or not clear) and the selected competitor solutions itself are not justified 
- Not enough experiments to support the proposed solution
- A lot of important research details are missing

## What is not a problem:
- It is fine when not all the fine-grained details of the experiments are covered, but the overall approach is clear

## Evaluation Guidelines:
- Always point to the exact slide where the issue or strength is observed
- Provide specific, actionable suggestions (e.g., "On Slide 5, the methodology is vague; specify the sample size and justify why it is sufficient")
- Provide concrete examples and suggestions for improvement
- Focus on research design principles (evidence-based approach, clarity of the proposed solution, scientific rigor)
- Only report issues you are confident about

## Response Format:
Your answer must contain two sections: "Thought" and "Answer".
Evaluate the presentation's research quality by examining the evidence-based approach to problem solving, the clarity of the proposed solution, and the scientific rigor of the research.
Provide specific suggestions for improving the research quality of the presentation.
In the Answer section, provide the final evaluation strictly following the format instructions.
"""
    
    # Define presentation type specific content
    type_specific_content = {
        PresentationType.SCIENTIFIC: """

""",
        PresentationType.INDUSTRIAL: """

""",
        PresentationType.COLLABORATIVE: """

""",
        PresentationType.TECHNOLOGICAL: """

""",
    }
    
    # Get specific content for the presentation type, or empty string if None
    specific_content = type_specific_content.get(presentation_type, "")
    
    # Format the prompt with the specific content
    return base_prompt.format(presentation_type_specific_content=specific_content)


# Default prompt for backward compatibility
prompt = generate_prompt()
