from pydantic import BaseModel
from dataclasses import dataclass
from typing import Literal, List, Optional

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

# Define standard slide types
SLIDE_TYPES = [
    "title",
    "separator", 
    "motivation",
    "goals",
    "tasks",
    "current_state",
    "proposed_solution",
    "experiment_settings",
    "experimental_results",
    "conclusion"
]

# Define criterion categories
CRITERION_CATEGORIES = [
    "visual",      # Visual design and layout
    "content",     # Content quality and clarity
    "structure",   # Structural organization
    "technical",   # Technical aspects
    "accessibility", # Accessibility and usability
    "general"      # General evaluation
]