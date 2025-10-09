import logging
from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Type
from textwrap import dedent

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable

from slideguard.schemes import Criteria
from slideguard.crew.controlled_llm import ControlledLLM


logger = logging.getLogger(__name__)

class CriterionInfo(BaseModel):
    criteria: Criteria
    type: Literal["slide", "deck"]
    criterion_description: str
    agent_prompt_template: str
    task_prompt_template: str
    pydantic: Type[BaseModel]
    # New fields for enhanced functionality
    applicable_slide_types: Optional[List[str]] = None  # If None, applies to all slide types
    priority: int = 1  # Priority for evaluation order (lower = higher priority)
    requires_slide_type: bool = False  # Whether this criterion requires slide type classification first
    category: str = "general"  # Category for grouping criteria (e.g., "visual", "content", "structure")

    @property
    def agent_prompt(self) -> str:
        # No schema insertion here; ControlledLLM appends format instructions itself
        return self.agent_prompt_template
    
    def to_runnable(self, llm: ControlledLLM) -> Runnable:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.agent_prompt),
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
