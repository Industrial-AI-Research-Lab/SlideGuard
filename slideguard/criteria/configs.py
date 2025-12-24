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

ABBREVIATIONS_WHITELIST = {
    'итмо', 'itmo', 'vitmo', 'json', 'phd', 'ai', 'ml', 'gan', 'gpt', 'cnn', 'lstm', 'rag', 'llm', 'graphrag', 'к.т.н.'
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
        applicability=Applicability(),
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
        applicability=Applicability(),
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
        applicability=Applicability(),
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
        applicability=Applicability(),
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
        applicability=Applicability(),
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
        applicability=Applicability(),
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
        applicability=Applicability(),
        postprocessor_funcs=[],
    ),
]

DEFAULT_CRITERIA_CONFIGS = [
    *PRESET_CRITERIA_CONFIGS,
    *SERVICE_CRITERIA_CONFIGS,
]