from pydantic import BaseModel
from typing import Literal, List, Optional, Type
from textwrap import dedent

from slideguard.schemes import Criteria

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
        return self.agent_prompt_template.format(schema_format=self.pydantic.model_json_schema())

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
