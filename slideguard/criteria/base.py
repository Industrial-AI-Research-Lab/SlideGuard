from pydantic import BaseModel
from dataclasses import dataclass
from typing import Literal, List, Optional, Type
from textwrap import dedent

from slideguard.schemes import Criteria

class CriterionInfo(BaseModel):
    criteria: Criteria
    type: Literal["slide", "deck"]
    criterion_description: str
    agent_prompt: str
    task_prompt: str
    pydantic: Type[BaseModel]
    # New fields for enhanced functionality
    applicable_slide_types: Optional[List[str]] = None  # If None, applies to all slide types
    priority: int = 1  # Priority for evaluation order (lower = higher priority)
    requires_slide_type: bool = False  # Whether this criterion requires slide type classification first
    category: str = "general"  # Category for grouping criteria (e.g., "visual", "content", "structure")

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
