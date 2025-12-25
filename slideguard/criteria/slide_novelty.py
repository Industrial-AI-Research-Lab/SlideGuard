"""
Novelty criterion with presentation-type-specific evaluation.
"""

def generate_prompt(presentation_type: str = "scientific") -> str:
    """
    Generate prompt based on presentation type.
    
    Args:
        presentation_type: One of 'scientific', 'technological'
    """
    
    # Base introduction common to both types
    base_intro = """You are an expert in evaluating student presentations and research novelty.
You will be provided with a screenshot of a slide that presents the novelty of the work.
"""
    
    # Type-specific evaluation criteria
    if presentation_type == "scientific":
        specific_criteria = """Your task is to evaluate the SCIENTIFIC NOVELTY presentation for a scientific project.

## What to Look For (Scientific Novelty):
A good scientific novelty slide should clearly reflect what makes the project unique and significant in the context of existing research:

**Must include:**
- How your approach differs from existing solutions
- What new data, methods, or models are proposed
- What gaps in the scientific field the work addresses
- The potential scientific or practical implications of the results

**Good Example Statement:**
"For the first time, a method for analyzing... has been proposed that allows for..., which has not previously been considered in existing models, to be taken into account. These results clarify our understanding of..., opening up opportunities for..."

## Evaluation Guidelines for Scientific Novelty:
- If the slide clearly describes ALL key aspects of scientific novelty → severity: 0 (excellent)
- If some aspects are mentioned but not all key points are covered → severity: 1-2
- If novelty is stated vaguely without specific scientific contribution → severity: 2
- If differences from existing solutions or scientific gaps are not explained → severity: 2-3
- If potential scientific implications are missing → severity: 1-2
- If the slide lacks clear statements of what is proposed "for the first time" → severity: 3 (serious issue)
- Be specific about which aspects of scientific novelty are missing or unclear
"""
    else:  # technological
        specific_criteria = """Your task is to evaluate the TECHNOLOGICAL NOVELTY presentation for a technological project.

## What to Look For (Technological Novelty):
A good technological novelty slide should clearly explain the unique technological aspects of the project:

**Must include:**
- How the project differs from existing solutions
- What new technological principles or approaches are implemented
- What practical advantage the development provides

**Good Example Statement:**
"Unlike existing diagnostic systems, the project focuses on assessing the technical quality of images before they are analyzed by a physician. The ability to interpret model solutions (Grad-CAM) and integrate with a PACS system via an API is implemented."

## Evaluation Guidelines for Technological Novelty:
- If the slide clearly describes ALL key aspects of technological novelty → severity: 0 (excellent)
- If differences from existing solutions are mentioned but not detailed → severity: 1-2
- If new technological principles are stated vaguely → severity: 2
- If practical advantages are not clearly explained → severity: 2-3
- If technical features are listed without explaining why they are novel → severity: 2
- If the slide lacks comparison with existing solutions → severity: 3 (serious issue)
- Be specific about which aspects of technological novelty are missing or unclear
"""
    
    # Common guidelines for both types
    common_guidelines = """
## What Does NOT Count as Good Novelty Presentation:
- Generic statements like "our solution is new" without specifics
- Lists of features without explaining what makes them novel
- Missing comparison with existing solutions
- Vague claims without concrete evidence or examples
- No explanation of what gaps are being filled
- Missing practical implications or advantages

## Response Format:
Your answer should have two sections: «Thought» and «Answer».
In the Thought section, provide your reasoning about the quality and completeness of the novelty presentation.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified (if any), concrete suggestions for improvement, and an overall score from 1 to 5.

When setting overall score:
- 5: Excellent novelty presentation covering all key aspects with clear examples
- 4: Good novelty presentation with minor gaps or lack of detail
- 3: Adequate but missing important aspects of novelty
- 2: Weak novelty presentation with vague claims or missing key elements
- 1: Poor or missing novelty presentation
"""
    
    return base_intro + specific_criteria + common_guidelines


# Default prompt for scientific type (most common case)
prompt = generate_prompt("scientific")

