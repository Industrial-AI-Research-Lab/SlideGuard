"""
Key Results criterion with presentation-type-specific evaluation.
"""

def generate_prompt(presentation_type: str = "scientific") -> str:
    """
    Generate prompt based on presentation type.
    
    Args:
        presentation_type: One of 'scientific', 'technological', 'collaborative', 'industrial'
    """
    
    # Base introduction common to all types
    base_intro = """You are an expert in evaluating student presentations and research outcomes.
You will be provided with a screenshot of a slide that presents the key results of the project.
"""
    
    # Type-specific evaluation criteria
    if presentation_type == "scientific":
        specific_criteria = """Your task is to evaluate the key results presentation for a SCIENTIFIC presentation.

## What to Look For (Scientific Project):
A good key results slide for scientific presentation should contain:
- Clear description of what was achieved by the end of the research project
- Practical result or benefit of the research
- Quantified accuracy metrics with specific values:
  * Accuracy on the test set (e.g., 92%)
  * F1-score for specific classes (e.g., 0.89)
  * ROC-AUC or other relevant metrics (e.g., 0.95)
  * Other domain-specific performance measures
- Link to an open repository containing:
  * Code for implementing the stated scientific task
  * Code for conducting experiments
  * Formatted README.MD describing the repository

## Evaluation Guidelines for Scientific:
- If the slide presents clear achievements AND quantified metrics (accuracy, F1, ROC-AUC, etc.) AND link to repository → severity: 0 (excellent)
- If achievements and metrics are present but repository link is missing → severity: 1-2
- If metrics are vague or not quantified (e.g., "good results" instead of "92% accuracy") → severity: 2
- If the benefit or practical result is unclear or missing → severity: 2-3
- If achievements are described but no metrics are provided → severity: 3 (serious issue)
- Be specific about what metrics or information are missing
"""
    elif presentation_type == "technological":
        specific_criteria = """Your task is to evaluate the key results presentation for a TECHNOLOGICAL presentation.

## What to Look For (Technological Project):
A good key results slide for technological presentation should contain:
- Clear description of what was achieved by the end of the research project
- Practical result or benefit (what problem does it solve?)
- Quantified metrics with specific values:
  * Accuracy or quality metrics (e.g., 91% classification accuracy)
  * Performance metrics (e.g., F1-score: 0.89)
  * Practical improvements (e.g., processing time, user experience)
  * System capabilities description
- Examples of how the system works (screenshots, demos, use cases)
- Link to an open repository containing:
  * Code for implementing the stated scientific task
  * Code for conducting experiments
  * Formatted README.MD describing the repository

## Evaluation Guidelines for Technological:
- If the slide presents achievements AND quantified metrics AND working examples AND repository link → severity: 0 (excellent)
- If achievements and metrics are present but repository link is missing → severity: 1-2
- If metrics are present but no working examples are shown → severity: 1-2
- If metrics are vague or benefits are unclear → severity: 2-3
- If no quantified metrics or practical results are provided → severity: 3 (serious issue)
- Be specific about what examples, metrics, or links are missing
"""
    elif presentation_type == "collaborative":
        specific_criteria = """Your task is to evaluate the key results presentation for a COLLABORATIVE presentation.

## What to Look For (Collaborative Project):
A good key results slide for collaborative presentation should contain:
- Achieved metrics with specific quantified values:
  * Performance metrics (e.g., 93% response accuracy)
  * Efficiency metrics (e.g., 0.7 seconds response time)
  * Practical improvements (e.g., 40% reduction in processing time)
  * User testing results (e.g., tested with 20 engineers)
- Practical effects and real-world impact
- Team engagement description:
  * How the team collaborated
  * Who was involved (partner organizations, users)
  * Testing and validation process
- Personal contribution:
  * Student's specific role and responsibilities
  * Individual achievements within the team effort
- Feedback and validation:
  * Positive feedback from partners/users
  * Pilot implementation status or approval
  * Real-world deployment evidence

## Evaluation Guidelines for Collaborative:
- If the slide presents quantified metrics AND practical effects AND team engagement AND personal contribution AND feedback → severity: 0 (excellent)
- If metrics are present but team engagement or personal contribution is unclear → severity: 1-2
- If feedback from partners is missing or not mentioned → severity: 2
- If metrics are vague or practical effects are not clear → severity: 2-3
- If personal contribution is not distinguished from team effort → severity: 2-3
- If no quantified metrics or validation evidence is provided → severity: 3 (serious issue)
- Be specific about what aspects (metrics, team engagement, personal contribution, feedback) are missing
"""
    else:  # industrial
        specific_criteria = """Your task is to evaluate the key results presentation for an INDUSTRIAL presentation.

## What to Look For (Industrial Project):
A good key results slide for industrial presentation should contain:
- Achieved metrics with specific quantified values:
  * Accuracy or prediction metrics (e.g., 95% failure prediction accuracy)
  * Performance metrics (e.g., recall rate 0.92)
  * Processing speed (e.g., 0.5 seconds on GPU)
  * Time benefits (e.g., detects wear 5-7 days before failure)
- Proof of applicability in real-world conditions:
  * Integration with industrial systems (e.g., SCADA via REST API)
  * Prototype deployment evidence
  * Real-world testing results
  * Industrial environment validation
- Link to an open repository containing (if possible):
  * Code for implementing the stated scientific problem
  * Code for conducting experiments
  * Formatted README.MD describing the repository
- MANDATORY: Link to a review from an industry representative:
  * Assessment of the solution to the stated problem
  * Evaluation of potential for using student's results
  * Partner company or organization name
  * Positive feedback or validation

## Evaluation Guidelines for Industrial:
- If the slide presents quantified metrics AND real-world proof AND repository link AND industry representative review → severity: 0 (excellent)
- If metrics and proof are present but industry representative review is missing → severity: 2-3 (this is MANDATORY)
- If repository link is missing → severity: 1 (it's "if possible", but encouraged)
- If metrics are vague or real-world applicability proof is weak → severity: 2-3
- If no integration with industrial systems or real-world validation is shown → severity: 3
- If industry representative review is missing → severity: 3 (serious issue, as it's mandatory)
- Be specific about what metrics, proof, links, or reviews are missing
"""
    
    # Common guidelines for all types
    common_guidelines = """
## What Does NOT Count as Good Key Results:
- Generic statements like "achieved good results" without quantified metrics
- Vague descriptions without specific numbers or measurements
- Missing links to code repositories (especially for scientific/technological)
- No practical demonstration or real-world validation
- Unclear benefit or impact of the results
- For collaborative: missing personal contribution or team engagement details
- For industrial: missing industry representative review (mandatory)

## Response Format:
Your answer should have two sections: «Thought» and «Answer».
In the Thought section, provide your reasoning about the quality of the key results presentation.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified (if any), concrete suggestions for improvement, and an overall score from 1 to 5.

When setting overall score:
- 5: Excellent key results with all required elements (metrics, proof, links, validation)
- 4: Good results with minor issues (e.g., some metrics could be more specific)
- 3: Adequate but missing some important elements (e.g., repository link or unclear metrics)
- 2: Weak results with significant gaps (e.g., vague metrics or missing validation)
- 1: Poor or missing key results information
"""
    
    return base_intro + specific_criteria + common_guidelines


# Default prompt for scientific type (most common case)
prompt = generate_prompt("scientific")

