from pydantic import BaseModel
from dataclasses import dataclass
from typing import Literal, List, Optional
from .slide_types import SlideType, slide_type_manager, get_slide_types, add_slide_type, validate_slide_type

@dataclass
class CriterionInfo:
    criterion_name: str
    criterion_type: Literal["slide", "deck"]
    criterion_description: str
    criterion_prompt: str
    criterion_schema: BaseModel
    # New fields for enhanced functionality
    applicable_slide_types: Optional[List[str]] = None  # If None, applies to all slide types
    priority: int = 1  # Priority for evaluation order (lower = higher priority)
    requires_slide_type: bool = False  # Whether this criterion requires slide type classification first
    category: str = "general"  # Category for grouping criteria (e.g., "visual", "content", "structure")

# Define standard slide types (backward compatibility)
SLIDE_TYPES = get_slide_types()

# Define criterion categories
CRITERION_CATEGORIES = [
    "visual",      # Visual design and layout
    "content",     # Content quality and clarity
    "structure",   # Structural organization
]