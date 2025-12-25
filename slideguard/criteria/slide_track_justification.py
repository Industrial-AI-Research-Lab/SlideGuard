"""
Track justification criterion with presentation-type-specific evaluation.
"""

def generate_prompt(presentation_type: str = "scientific") -> str:
    """
    Generate prompt based on presentation type.
    
    Args:
        presentation_type: One of 'scientific', 'technological', 'collaborative', 'industrial'
    """
    
    # Base introduction common to all types
    base_intro = """You are an expert in evaluating student presentations and project problem statements.
You will be provided with a screenshot of a slide that presents the problem being solved.
"""
    
    # Type-specific evaluation criteria
    if presentation_type == "scientific":
        specific_criteria = """Your task is to evaluate the problem statement and track justification for a SCIENTIFIC presentation.

## What to Look For (Scientific Track):
A good problem statement slide for scientific presentation should contain:
- Description of the problem being solved
- Justification of its relevance and importance
- Justification of its SCIENTIFIC NATURE (why the scientific track?)
- Explanation of scientific novelty or research contribution
- References to scientific principles, research questions, or academic goals
- How this problem contributes to scientific knowledge

## Evaluation Guidelines for Scientific:
- If the slide clearly describes the problem AND justifies its scientific nature → severity: 0 (excellent)
- If problem is described but scientific justification is weak or unclear → severity: 1-2
- If scientific nature is not clearly justified (why scientific vs. other tracks?) → severity: 2-3
- If problem description is missing or scientific relevance is absent → severity: 3 (serious issue)
- Be specific about what aspects of scientific justification are missing
"""
    elif presentation_type == "collaborative":
        specific_criteria = """Your task is to evaluate the problem statement and track justification for a COLLABORATIVE presentation.

## What to Look For (Collaborative Track):
A good problem statement slide for collaborative presentation should contain:
- Description of the problem being solved
- Justification of its overall relevance and significance
- Justification for the TEAM BEING COLLABORATED WITH (why a collaborative track?)
- Explanation of how collaboration addresses the problem
- Description of collaborative aspects and partner involvement
- How the problem requires or benefits from collaboration

## Evaluation Guidelines for Collaborative:
- If the slide clearly describes the problem AND justifies the collaborative nature → severity: 0 (excellent)
- If problem is described but collaborative justification is weak or unclear → severity: 1-2
- If collaborative nature is not clearly justified (why collaboration is needed?) → severity: 2-3
- If problem description is missing or collaborative relevance is absent → severity: 3 (serious issue)
- Be specific about what aspects of collaborative justification are missing
"""
    elif presentation_type == "industrial":
        specific_criteria = """Your task is to evaluate the problem statement and track justification for an INDUSTRIAL presentation.

## What to Look For (Industrial Track):
A good problem statement slide for industrial presentation should contain:
- Description of the problem being solved
- Justification of its relevance to INDUSTRY (why the industrial track?)
- Explanation of industrial application and practical impact
- How the problem affects real-world industrial processes or businesses
- Connection to industry needs and requirements
- Potential industrial value or market relevance

## Evaluation Guidelines for Industrial:
- If the slide clearly describes the problem AND justifies its industrial relevance → severity: 0 (excellent)
- If problem is described but industrial justification is weak or unclear → severity: 1-2
- If industrial relevance is not clearly justified (why industrial vs. other tracks?) → severity: 2-3
- If problem description is missing or industrial relevance is absent → severity: 3 (serious issue)
- Be specific about what aspects of industrial justification are missing
"""
    else:  # technological
        specific_criteria = """Your task is to evaluate the problem statement and track justification for a TECHNOLOGICAL presentation.

## What to Look For (Technological Track):
A good problem statement slide for technological presentation should contain:
- Description of the problem being solved
- Justification of its TECHNOLOGICAL RELEVANCE (why the technology track?)
- Explanation of technological innovation or advancement
- How the problem requires or benefits from technological solutions
- Description of technical challenges being addressed
- Connection to technological development and innovation

## Evaluation Guidelines for Technological:
- If the slide clearly describes the problem AND justifies its technological relevance → severity: 0 (excellent)
- If problem is described but technological justification is weak or unclear → severity: 1-2
- If technological relevance is not clearly justified (why technological vs. other tracks?) → severity: 2-3
- If problem description is missing or technological relevance is absent → severity: 3 (serious issue)
- Be specific about what aspects of technological justification are missing
"""
    
    # Common guidelines for all types
    common_guidelines = """
## What Does NOT Count as Good Track Justification:
- Generic problem descriptions without track-specific justification
- Vague statements about importance without explaining WHY this specific track
- Missing connection between the problem and the chosen track
- Simply stating "this is a {{track}} project" without justification

## Response Format:
Your answer should have two sections: «Thought» and «Answer».
In the Thought section, provide your reasoning about the quality of the problem statement and track justification.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified (if any), concrete suggestions for improvement, and an overall score from 1 to 5.

When setting overall score:
- 5: Excellent problem statement with clear track justification
- 4: Good problem statement with minor issues in justification
- 3: Adequate problem statement but weak track justification
- 2: Weak problem statement or missing track justification
- 1: Poor or missing problem statement and track justification
"""
    
    return base_intro + specific_criteria + common_guidelines


# Default prompt for scientific type (most common case)
prompt = generate_prompt("scientific")

