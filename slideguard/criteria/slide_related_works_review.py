"""
Related Works Review criterion with presentation-type-specific evaluation.
"""

def generate_prompt(presentation_type: str = "scientific") -> str:
    """
    Generate prompt based on presentation type.
    
    Args:
        presentation_type: One of 'scientific', 'technological', 'collaborative', 'industrial'
    """
    
    # Base introduction common to all types
    base_intro = """You are an expert in evaluating student presentations and related works analysis.
You will be provided with a screenshot of a slide that presents the current state of the field.
"""
    
    # Type-specific evaluation criteria
    if presentation_type == "scientific":
        specific_criteria = """Your task is to check if the slide adequately presents related works for a SCIENTIFIC presentation.

## What to Look For (Scientific Presentation):
A good related works slide for scientific presentation should contain:
- Presentation of 3-5 relevant papers/articles with their approaches
- Clear description of each approach's methodology
- Explicit mention of limitations of each presented work
- How these limitations justify the novelty of the current work
- Proper academic citations or references to the works

## Evaluation Guidelines for Scientific:
- If the slide presents 3-5 papers with approaches AND their limitations that justify novelty → severity: 0 (excellent)
- If papers are presented but limitations are unclear or not linked to novelty → severity: 1-2
- If fewer than 3 papers or more than 5 papers are presented → severity: 2
- If limitations are not mentioned or novelty justification is missing → severity: 3 (serious issue)
- Be specific about what is missing (number of papers, limitations, novelty justification)
"""
    else:
        # For technological, collaborative, and industrial - all use the same criteria
        specific_criteria = """Your task is to check if the slide adequately presents related works comparison.

## What to Look For (Technological/Industrial/Collaborative Presentation):
A good related works slide should contain:
- Brief and clear comparison of existing solutions
- Key criteria used for comparison that show:
  * How existing solutions are similar to each other
  * What their limitations are
  * Why your model/solution is better/newer/more useful
- Clear differentiation of the proposed solution from existing ones
- Specific points of improvement or advantages

## Evaluation Guidelines:
- If solutions are compared with clear criteria showing similarities, limitations, and advantages → severity: 0 (excellent)
- If comparison lacks clarity or misses one aspect (similarities/limitations/advantages) → severity: 1-2
- If comparison is too generic or criteria are not well-defined → severity: 2
- If no clear comparison or justification of why the solution is better → severity: 3 (serious issue)
- Be specific about what aspects of the comparison are missing or need improvement
"""
    
    # Common guidelines for all types
    common_guidelines = """
## What Does NOT Count as Good Related Works Review:
- Simple listing of solutions without comparison
- Generic descriptions without specific criteria
- Missing limitations analysis
- No justification for the proposed approach
- Vague statements like "our solution is better" without evidence

## Response Format:
Your answer should have two sections: «Thought» and «Answer».
In the Thought section, provide your reasoning about the quality of the related works review.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified (if any), concrete suggestions for improvement, and an overall score from 1 to 5.

When setting overall score:
- 5: Excellent related works review with all required elements
- 4: Good review with minor issues
- 3: Adequate but missing some important elements
- 2: Weak review with significant gaps
- 1: Poor or missing related works review
"""
    
    return base_intro + specific_criteria + common_guidelines


# Default prompt for scientific type (most common case)
prompt = generate_prompt("scientific")

