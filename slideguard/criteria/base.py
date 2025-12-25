import logging
from pydantic import BaseModel, Field
from typing import List, Optional, Type, Callable, Union
from textwrap import dedent

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from slideguard.schemes import Criteria
from slideguard.crew.controlled_llm import ControlledLLM
from slideguard.criteria.types import CriteriaTarget, PostProcessorFunc
from slideguard.criteria.presentation_types import PresentationType


logger = logging.getLogger(__name__)

class CriterionInfo(BaseModel):
    criteria: Criteria
    type: CriteriaTarget
    criterion_description: str
    agent_prompt_template: Union[str, Callable[[Optional[PresentationType]], str]]  # Can be string or function
    task_prompt_template: str
    pydantic: Type[BaseModel]
    # New fields for enhanced functionality
    applicable_slide_types: Optional[List[str]] = None  # If None, applies to all slide types
    exclude_slide_types: Optional[List[str]] = None  # If None, applies to all slide types
    applicable_presentation_types: Optional[List[PresentationType]] = None
    exclude_presentation_types: Optional[List[PresentationType]] = None
    priority: int = 1  # Priority for evaluation order (lower = higher priority)
    requires_infographics: bool = False  # Whether this criterion requires infographics classification first
    category: str = "general"  # Category for grouping criteria (e.g., "visual", "content", "structure")
    postprocessors: List[PostProcessorFunc] = Field(default_factory=list)  # List of post-processor functions

    class Config:
        arbitrary_types_allowed = True

    def get_agent_prompt(self, presentation_type: Optional[PresentationType] = None) -> str:
        """Get agent prompt, handling both string templates and generator functions"""
        if callable(self.agent_prompt_template):
            return self.agent_prompt_template(presentation_type)
        return self.agent_prompt_template
    
    def to_runnable(self, llm: ControlledLLM, presentation_type: Optional[PresentationType] = None) -> Runnable:
        agent_prompt = self.get_agent_prompt(presentation_type)
        prompt = ChatPromptTemplate.from_messages([
            ("system", agent_prompt),
            ("user", self.task_prompt_template),
        ])
        return prompt | llm.with_structured_output_retry(self.pydantic)
        

class BaseAttributes(BaseModel):
    severity: int = Field(description="Severity of the issue: 0 - no issues found, 1 - minor, 2 - moderate, 3 - serious", ge=0, le=3)


# Define criterion categories
CRITERION_CATEGORIES = [
    "visual",      # Visual design and layout
    "content",     # Content quality and clarity
    "structure",   # Structural organization
]

BASE_SLIDE_TASK_PROMPT = dedent(
    """
    Analyze this slide image.                
    ```image {slide_image_path} ```
    """
)

BASE_DECK_TASK_PROMPT = dedent(
    """
    Analyze this deck.                
    {deck_description} 
    """
)
