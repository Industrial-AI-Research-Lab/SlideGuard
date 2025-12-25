from slideguard.schemes import Criteria
from slideguard.criteria.base import BASE_SLIDE_TASK_PROMPT, BASE_DECK_TASK_PROMPT
from slideguard.criteria.factory import CriterionConfig
from slideguard.criteria.types import (
    Applicability,
    OutputSpec,
    ScoredListItemSpec,
    PostProcessorContext,
    OutputKind,
    CriteriaTarget,
    ALL_PRESENTATION_TYPES,
    PresentationType,
)
from slideguard.criteria.postprocessors import filter_sort_by_severity, abbreviations_whitelist
from slideguard.criteria.slide_types import SlideType, generate_slide_helper_type_prompt
from slideguard.criteria.slide_helper_description import prompt as slide_helper_description_prompt
from slideguard.schemes import SlideType as SlideTypeModel, SlideDescription

from slideguard.criteria.slide_graphic_content_match import prompt as slide_graphic_content_match_prompt
from slideguard.criteria.slide_abbreviations import prompt as slide_abbreviations_prompt
from slideguard.criteria.slide_fact_link_availability import prompt as slide_fact_link_availability_prompt
from slideguard.criteria.slide_orphography_correctness import prompt as slide_orphography_correctness_prompt
from slideguard.criteria.slide_title_content_match import prompt as slide_title_content_match_prompt
from slideguard.criteria.slide_title_slide_quality import prompt as slide_title_slide_quality_prompt
from slideguard.criteria.slide_visual_arrangement import prompt as slide_visual_arrangement_prompt
from slideguard.criteria.deck_storytelling import generate_prompt as deck_storytelling_generate_prompt
from slideguard.criteria.deck_structure_analysis import generate_prompt as deck_structure_analysis_generate_prompt
from slideguard.criteria.deck_research_quality import generate_prompt as deck_research_quality_generate_prompt
from slideguard.criteria.slide_track_justification import generate_prompt as generate_track_justification_prompt
from slideguard.criteria.slide_novelty import generate_prompt as generate_novelty_prompt
from slideguard.criteria.slide_related_works_review import generate_prompt as generate_related_works_prompt
from slideguard.criteria.slide_industrial_applicability import prompt as slide_industrial_applicability_prompt
from slideguard.criteria.slide_key_results import generate_prompt as generate_key_results_prompt

ABBREVIATIONS_WHITELIST = {
    'итмо', 'itmo', 'iTMO', 'vitmo', 'json', 'phd', 'ai', 'ml', 'gan', 'gpt', 'cnn', 'lstm', 'rag', 'llm', 'graphrag', 'к.т.н.'
}


def make_abbreviations_postprocessor(result, ctx):
    new_ctx = PostProcessorContext(
        criteria_id=ctx.criteria_id,
        params={"whitelist": ABBREVIATIONS_WHITELIST}
    )
    return abbreviations_whitelist(result, new_ctx)


PRESET_CRITERIA_CONFIGS = [
    CriterionConfig(
        id=Criteria.slide_graphic_content_match,
        target=CriteriaTarget.slide,
        description="Analyzing whether graphic content matches the slide content and provide appropriate suggestions",
        agent_prompt_template=slide_graphic_content_match_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Comment on the slide issue",
                suggestion_description="Suggestion for the slide",
            ),
        ),
        priority=4,
        category="visual",
        applicability=Applicability(
            exclude_slide_types=[SlideType.TITLE_SLIDE, SlideType.END_SLIDE, SlideType.SEPARATOR],
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
            requires_infographics=True,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_abbreviations,
        target=CriteriaTarget.slide,
        description="Detect unexplained abbreviations on the slide",
        agent_prompt_template=slide_abbreviations_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Found abbreviation (write here ONLY the abbreviation exactly as it appeared in the text, and nothing else)",
                suggestion_description="<Specify that it needs to be explained>",
            ),
        ),
        priority=4,
        category="content",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[make_abbreviations_postprocessor, filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_fact_link_availability,
        target=CriteriaTarget.slide,
        description="Analyzing whether fact links are available on the slide and provide appropriate suggestions",
        agent_prompt_template=slide_fact_link_availability_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(kind=OutputKind.scored_list),
        priority=4,
        category="visual",
        applicability=Applicability(
            applicable_slide_types=[SlideType.CURRENT_STATE, SlideType.PROPOSED_SOLUTION, SlideType.EXPERIMENTAL_RESULTS, SlideType.EXPERIMENT_SETTINGS, SlideType.MOTIVATION],
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_orphography_correctness,
        target=CriteriaTarget.slide,
        description="Analyzing whether the slide has any typographical or grammatical errors and provide appropriate suggestions",
        agent_prompt_template=slide_orphography_correctness_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Found Orphographic or grammatical error",
                suggestion_description="Fix the word <<incorrect word>>",
            ),
        ),
        priority=4,
        category="visual",
        applicability=Applicability(
            exclude_slide_types=[SlideType.END_SLIDE, SlideType.TITLE_SLIDE],
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_title_content_match,
        target=CriteriaTarget.slide,
        description="Analyzing whether slide titles match their content and provide appropriate suggestions",
        agent_prompt_template=slide_title_content_match_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(kind=OutputKind.scored_list),
        priority=3,
        category="visual",
        applicability=Applicability(
            exclude_slide_types=[SlideType.TITLE_SLIDE, SlideType.END_SLIDE, SlideType.SEPARATOR],
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_title_slide_quality,
        target=CriteriaTarget.slide,
        description="Analyzing whether the slide title matches the slide quality",
        agent_prompt_template=slide_title_slide_quality_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(kind=OutputKind.scored_list),
        priority=4,
        category="visual",
        applicability=Applicability(
            applicable_slide_types=[SlideType.TITLE_SLIDE],
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_visual_arrangement,
        target=CriteriaTarget.slide,
        description="Visual arrangement of the slide",
        agent_prompt_template=slide_visual_arrangement_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Comment on the slide issue",
                suggestion_description="Suggestion for the slide",
            ),
        ),
        priority=2,
        category="visual",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_track_justification_scientific,
        target=CriteriaTarget.slide,
        description="Analyzing problem statement and justification of its scientific nature for scientific presentations",
        agent_prompt_template=generate_track_justification_prompt("scientific"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with problem statement or track justification",
                suggestion_description="Suggestion for improving problem description and scientific justification",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.PROBLEM_STATEMENT],
            applicable_presentation_types=[PresentationType.SCIENTIFIC],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_track_justification_collaborative,
        target=CriteriaTarget.slide,
        description="Analyzing problem statement and justification of collaborative nature for collaborative presentations",
        agent_prompt_template=generate_track_justification_prompt("collaborative"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with problem statement or track justification",
                suggestion_description="Suggestion for improving problem description and collaborative justification",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.PROBLEM_STATEMENT],
            applicable_presentation_types=[PresentationType.COLLABORATIVE],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_track_justification_industrial,
        target=CriteriaTarget.slide,
        description="Analyzing problem statement and justification of industrial relevance for industrial presentations",
        agent_prompt_template=generate_track_justification_prompt("industrial"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with problem statement or track justification",
                suggestion_description="Suggestion for improving problem description and industrial justification",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.PROBLEM_STATEMENT],
            applicable_presentation_types=[PresentationType.INDUSTRIAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_track_justification_technological,
        target=CriteriaTarget.slide,
        description="Analyzing problem statement and justification of technological relevance for technological presentations",
        agent_prompt_template=generate_track_justification_prompt("technological"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with problem statement or track justification",
                suggestion_description="Suggestion for improving problem description and technological justification",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.PROBLEM_STATEMENT],
            applicable_presentation_types=[PresentationType.TECHNOLOGICAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_novelty_scientific,
        target=CriteriaTarget.slide,
        description="Analyzing the quality of scientific novelty presentation",
        agent_prompt_template=generate_novelty_prompt("scientific"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with scientific novelty presentation",
                suggestion_description="Suggestion for improving scientific novelty description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.SCIENTIFIC_NOVELTY],
            applicable_presentation_types=[PresentationType.SCIENTIFIC],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_novelty_technological,
        target=CriteriaTarget.slide,
        description="Analyzing the quality of technological novelty presentation",
        agent_prompt_template=generate_novelty_prompt("technological"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with technological novelty presentation",
                suggestion_description="Suggestion for improving technological novelty description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.TECHNOLOGICAL_NOVELTY],
            applicable_presentation_types=[PresentationType.TECHNOLOGICAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_related_works_review_scientific,
        target=CriteriaTarget.slide,
        description="Analyzing the quality of related works review for scientific presentations (3-5 papers with limitations)",
        agent_prompt_template=generate_related_works_prompt("scientific"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with related works review",
                suggestion_description="Suggestion for improving related works presentation",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.CURRENT_STATE],
            applicable_presentation_types=[PresentationType.SCIENTIFIC],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_related_works_review_technological,
        target=CriteriaTarget.slide,
        description="Analyzing the quality of related works comparison for technological presentations",
        agent_prompt_template=generate_related_works_prompt("technological"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with related works comparison",
                suggestion_description="Suggestion for improving solutions comparison",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.CURRENT_STATE],
            applicable_presentation_types=[PresentationType.TECHNOLOGICAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_related_works_review_collaborative,
        target=CriteriaTarget.slide,
        description="Analyzing the quality of related works comparison for collaborative presentations",
        agent_prompt_template=generate_related_works_prompt("collaborative"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with related works comparison",
                suggestion_description="Suggestion for improving solutions comparison",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.CURRENT_STATE],
            applicable_presentation_types=[PresentationType.COLLABORATIVE],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_related_works_review_industrial,
        target=CriteriaTarget.slide,
        description="Analyzing the quality of related works comparison for industrial presentations",
        agent_prompt_template=generate_related_works_prompt("industrial"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with related works comparison",
                suggestion_description="Suggestion for improving solutions comparison",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.CURRENT_STATE],
            applicable_presentation_types=[PresentationType.INDUSTRIAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_industrial_applicability,
        target=CriteriaTarget.slide,
        description="Analyzing industrial applicability: where/how the project can be implemented, economic and technological impact",
        agent_prompt_template=slide_industrial_applicability_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with industrial applicability presentation",
                suggestion_description="Suggestion for improving industrial applicability description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.INDUSTRIAL_APPLICABILITY],
            applicable_presentation_types=[PresentationType.INDUSTRIAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_key_results_scientific,
        target=CriteriaTarget.slide,
        description="Analyzing key results for scientific presentations: achieved metrics, practical results, and repository links",
        agent_prompt_template=generate_key_results_prompt("scientific"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with key results presentation",
                suggestion_description="Suggestion for improving key results description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.KEY_RESULTS],
            applicable_presentation_types=[PresentationType.SCIENTIFIC],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_key_results_technological,
        target=CriteriaTarget.slide,
        description="Analyzing key results for technological presentations: achieved metrics, practical benefits, working examples, and repository links",
        agent_prompt_template=generate_key_results_prompt("technological"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with key results presentation",
                suggestion_description="Suggestion for improving key results description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.KEY_RESULTS],
            applicable_presentation_types=[PresentationType.TECHNOLOGICAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_key_results_collaborative,
        target=CriteriaTarget.slide,
        description="Analyzing key results for collaborative presentations: achieved metrics, team engagement, personal contribution, and feedback",
        agent_prompt_template=generate_key_results_prompt("collaborative"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with key results presentation",
                suggestion_description="Suggestion for improving key results description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.KEY_RESULTS],
            applicable_presentation_types=[PresentationType.COLLABORATIVE],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.slide_key_results_industrial,
        target=CriteriaTarget.slide,
        description="Analyzing key results for industrial presentations: achieved metrics, real-world proof, repository links, and mandatory industry representative review",
        agent_prompt_template=generate_key_results_prompt("industrial"),
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue with key results presentation",
                suggestion_description="Suggestion for improving key results description",
            ),
        ),
        priority=3,
        category="content",
        applicability=Applicability(
            applicable_slide_types=[SlideType.KEY_RESULTS],
            applicable_presentation_types=[PresentationType.INDUSTRIAL],
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.deck_storytelling,
        target=CriteriaTarget.deck,
        description="Evaluating the storytelling quality of students' presentations",
        agent_prompt_template=deck_storytelling_generate_prompt,
        task_prompt_template=BASE_DECK_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue description",
                suggestion_description="Detailed description of the issue and suggestion for improvement",
            ),
        ),
        priority=1,
        category="structure",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.deck_structure_analysis,
        target=CriteriaTarget.deck,
        description="Evaluating the completeness of presentation structure",
        agent_prompt_template=deck_structure_analysis_generate_prompt,
        task_prompt_template=BASE_DECK_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue description",
                suggestion_description="Detailed description of the issue and suggestion for improvement",
            ),
        ),
        priority=1,
        category="structure",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),

    CriterionConfig(
        id=Criteria.deck_research_quality,
        target=CriteriaTarget.deck,
        description="Evaluating the research quality of students' presentations",
        agent_prompt_template=deck_research_quality_generate_prompt,
        task_prompt_template=BASE_DECK_TASK_PROMPT,
        output=OutputSpec(
            kind=OutputKind.scored_list,
            item_spec=ScoredListItemSpec(
                element_description="Issue description",
                suggestion_description="Detailed description of the issue and suggestion for improvement",
            ),
        ),
        priority=3,
        category="research",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[filter_sort_by_severity],
    ),
]

SERVICE_CRITERIA_CONFIGS = [
    CriterionConfig(
        id=Criteria.slide_type,
        target=CriteriaTarget.slide,
        description="Type of the slide",
        # Pass function here so that prompt can be adapted based on PresentationType
        agent_prompt_template=generate_slide_helper_type_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(kind=OutputKind.custom),
        output_model=SlideTypeModel,
        priority=0,
        category="service",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[],
    ),

    CriterionConfig(
        id=Criteria.slide_description,
        target=CriteriaTarget.slide,
        description="Detailed description of the slide, including description of all charts, tables and illustrations and how they are arranged",
        agent_prompt_template=slide_helper_description_prompt,
        task_prompt_template=BASE_SLIDE_TASK_PROMPT,
        output=OutputSpec(kind=OutputKind.custom),
        output_model=SlideDescription,
        priority=0,
        category="service",
        applicability=Applicability(
            applicable_presentation_types=ALL_PRESENTATION_TYPES,
        ),
        postprocessor_funcs=[],
    ),
]

DEFAULT_CRITERIA_CONFIGS = [
    *PRESET_CRITERIA_CONFIGS,
    *SERVICE_CRITERIA_CONFIGS,
]