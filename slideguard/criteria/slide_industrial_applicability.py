"""
Industrial Applicability criterion for industrial presentations.
"""

def generate_prompt() -> str:
    """
    Generate prompt for evaluating industrial applicability slide.
    
    This criterion is only applicable to industrial presentations.
    """
    
    prompt = """You are an expert in evaluating student presentations on industrial projects.
You will be provided with a screenshot of a slide that presents the potential for using obtained results in industry.

## What to Look For (Industrial Applicability):
A good industrial applicability slide should contain:
- Clear description of WHERE and HOW the project can be implemented in industry
- Economic impact: quantified potential benefits (e.g., cost reduction, efficiency improvements)
- Technological impact: improvements to processes, systems, or products
- Specific application areas (examples):
  * Oil and gas and energy industries
  * Metallurgy and mining
  * Mechanical engineering and transport infrastructure
  * Manufacturing and production
  * Or other relevant industrial sectors
- Potential impact with specific metrics (examples):
  * Reduction of unscheduled equipment downtime (e.g., by up to 30%)
  * Extension of bearing and component life (e.g., by 20-25%)
  * Reduction in scheduled maintenance costs
  * Possibility of integration into existing systems (e.g., SCADA systems)
- Link to a free-form description of the industrial project:
  * Preprint of a technology
  * Popular science article
  * Technical report
  * Can be in Russian or English

## Evaluation Guidelines:
- If the slide clearly describes WHERE/HOW to implement AND shows economic/technological impact with specific metrics AND provides a link to project description → severity: 0 (excellent)
- If implementation description is present but lacks specific metrics or quantified impact → severity: 1
- If application areas are mentioned but economic/technological impact is vague or not quantified → severity: 2
- If only general statements about applicability without specific implementation details or impact metrics → severity: 2-3
- If link to project description (preprint/article/report) is missing → severity: 1-2 (depending on other content)
- If the slide is missing critical elements (implementation details, impact metrics, or application areas) → severity: 3 (serious issue)
- Be specific about what aspects are missing or need improvement

## What Does NOT Count as Good Industrial Applicability:
- Generic statements like "can be used in industry" without specific areas
- Vague impact descriptions without quantified metrics
- Missing implementation details (WHERE and HOW)
- No reference to economic or technological benefits
- Missing link to detailed project description
- Only theoretical benefits without practical application context

## Response Format:
Your answer should have two sections: «Thought» and «Answer».
In the Thought section, provide your reasoning about the quality of the industrial applicability presentation.
In the Answer section, return the final evaluation strictly following the format instructions with specific issues identified (if any), concrete suggestions for improvement, and an overall score from 1 to 5.

When setting overall score:
- 5: Excellent industrial applicability with all required elements (implementation, impact metrics, areas, link)
- 4: Good presentation with minor issues (e.g., some metrics could be more specific)
- 3: Adequate but missing some important elements (e.g., vague metrics or missing link)
- 2: Weak presentation with significant gaps (e.g., no quantified impact or unclear implementation)
- 1: Poor or missing industrial applicability information
"""
    
    return prompt


# Default prompt
prompt = generate_prompt()

