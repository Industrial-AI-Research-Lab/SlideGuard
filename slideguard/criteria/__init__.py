from slideguard.criteria.deck_research_quality import DECK_RESEARCH_QUALITY
from slideguard.criteria.deck_storytelling import DECK_STORYTELLING
from slideguard.criteria.deck_structure_analysis import DECK_STRUCTURE_ANALYSIS
from slideguard.criteria.slide_abbreviations import SLIDE_ABBREVIATIONS
from slideguard.criteria.slide_color_and_fonts import SLIDE_COLOR_AND_FONTS
from slideguard.criteria.slide_fact_link_availability import SLIDE_FACT_LINK_AVAILABILITY
from slideguard.criteria.slide_graphic_content_match import SLIDE_GRAPHIC_CONTENT_MATCH
from slideguard.criteria.slide_helper_description import SLIDE_HELPER_DESCRIPTION
from slideguard.criteria.slide_helper_type import SLIDE_HELPER_TYPE
from slideguard.criteria.slide_orphography_correctness import SLIDE_ORPHOGRAPHY_CORRECTNESS
from slideguard.criteria.slide_title_content_match import SLIDE_TITLE_CONTENT_MATCH
from slideguard.criteria.slide_title_slide_quality import SLIDE_TITLE_SLIDE_QUALITY
from slideguard.criteria.slide_visual_arrangement import SLIDE_VISUAL_ARRANGEMENT
from slideguard.schemes import Criteria

SLIDE_CRITERIA_INFO = {
   Criteria.slide_type: SLIDE_HELPER_TYPE,
   Criteria.slide_description: SLIDE_HELPER_DESCRIPTION,
   Criteria.slide_visual_arrangement: SLIDE_VISUAL_ARRANGEMENT,
   Criteria.slide_color_and_fonts: SLIDE_COLOR_AND_FONTS,
   Criteria.slide_abbreviations: SLIDE_ABBREVIATIONS,
   Criteria.slide_fact_link_availability: SLIDE_FACT_LINK_AVAILABILITY,
   Criteria.slide_graphic_content_match: SLIDE_GRAPHIC_CONTENT_MATCH,
   Criteria.slide_orphography_correctness: SLIDE_ORPHOGRAPHY_CORRECTNESS,
   Criteria.slide_title_content_match: SLIDE_TITLE_CONTENT_MATCH,
   Criteria.slide_title_slide_quality: SLIDE_TITLE_SLIDE_QUALITY,
}

DECK_CRITERIA_INFO = {
   Criteria.deck_storytelling: DECK_STORYTELLING,
   Criteria.deck_structure_analysis: DECK_STRUCTURE_ANALYSIS,
   Criteria.deck_research_quality: DECK_RESEARCH_QUALITY,
}

