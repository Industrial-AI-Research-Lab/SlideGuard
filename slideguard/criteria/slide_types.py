"""
Slide Type Management System

This module provides a convenient way to manage slide types in SlideGuard.
It allows for easy extension, validation, and querying of slide types.
"""

from typing import List, Optional, Set, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
import json
from pathlib import Path

class SlideType(Enum):
    """Enum for slide types to provide type safety and better IDE support"""
    TITLE_SLIDE = "Title slide"
    SEPARATOR = "Separator"
    MOTIVATION = "Motivation"
    GOAL = "Goal"
    TASKS = "Tasks"
    CURRENT_STATE = "Current State"
    PROPOSED_SOLUTION = "Proposed Solution"
    EXPERIMENT_SETTINGS = "Experiment Settings"
    EXPERIMENTAL_RESULTS = "Experimental Results"
    CONCLUSION = "Conclusion"
    END_SLIDE = "End slide"
    Q_AND_A = "Q&A"
    SCIENTIFIC_TRACK_JUSTIFICATION = "Scientific Track Justification"

@dataclass
class SlideTypeInfo:
    """Information about a slide type"""
    name: str
    description: str
    category: str = "general"
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

class SlideTypeManager:
    """Manager for slide types with convenient extension methods"""
    
    def __init__(self):
        self._slide_types: Dict[str, SlideTypeInfo] = {}
        self._load_default_types()
    
    def _load_default_types(self):
        """Load default slide types with detailed descriptions matching slide_helper_type prompt"""
        default_types = {
            SlideType.TITLE_SLIDE.value: SlideTypeInfo(
                name=SlideType.TITLE_SLIDE.value,
                description="this is the first slide of the presentation. It usually contains the title of the presentation and the name of the presenter and scientific advisor.",
                category="structure"
            ),
            SlideType.SEPARATOR.value: SlideTypeInfo(
                name=SlideType.SEPARATOR.value,
                description="this is a slide that separates logical sections of the presentation. Usually contains only a title or title and illustration.",
                category="structure"
            ),
            SlideType.MOTIVATION.value: SlideTypeInfo(
                name=SlideType.MOTIVATION.value,
                description="this is a slide that contains information about the motivation for the project.",
                category="content"
            ),
            SlideType.CURRENT_STATE.value: SlideTypeInfo(
                name=SlideType.CURRENT_STATE.value,
                description="this is a slide that contains information about the current state of the field and existing products / methods / solutions.",
                category="content"
            ),
            SlideType.GOAL.value: SlideTypeInfo(
                name=SlideType.GOAL.value,
                description="slide that contain information about goals that need to be achieved to implement the project or product, which is the subject of the entire presentation. Goals must be EXPLICITLY FORMULATED. Remember that goals can only be statements (including those transmitted through infographic) ALWAYS directed into the future. Information about past results, achievements, experience, about what has already been done, CANNOT be a goal.",
                category="content"
            ),
            SlideType.TASKS.value: SlideTypeInfo(
                name=SlideType.TASKS.value,
                description="slide that contain information about tasks that need to be performed to implement the project or product, which is the subject of the entire presentation. Differ from goals in that they describe actions, not the final state to which you need to go.",
                category="content"
            ),
            SlideType.PROPOSED_SOLUTION.value: SlideTypeInfo(
                name=SlideType.PROPOSED_SOLUTION.value,
                description="this is a slide that contains information about the proposed solution to the problem. Can be shown as a workflow or a diagram with description.",
                category="content"
            ),
            SlideType.EXPERIMENT_SETTINGS.value: SlideTypeInfo(
                name=SlideType.EXPERIMENT_SETTINGS.value,
                description="slide with description of used for experiments datasets or description of hyperparameters of used methods and models.",
                category="technical"
            ),
            SlideType.EXPERIMENTAL_RESULTS.value: SlideTypeInfo(
                name=SlideType.EXPERIMENTAL_RESULTS.value,
                description="this is a slide that contains information about the experimental results that show the effectiveness of the proposed solution.",
                category="content"
            ),
            SlideType.CONCLUSION.value: SlideTypeInfo(
                name=SlideType.CONCLUSION.value,
                description="this is a slide that contains information about the conclusion of the presentation.",
                category="content"
            ),
            SlideType.END_SLIDE.value: SlideTypeInfo(
                name=SlideType.END_SLIDE.value,
                description="this is a slide that identifies the end of the presentation. It usually contains a thank you message for the audience.",
                category="content"
            ),
            SlideType.Q_AND_A.value: SlideTypeInfo(
                name=SlideType.Q_AND_A.value,
                description="this is a slide that contains the question and answer session.",
                category="interactive"
            ),
            SlideType.SCIENTIFIC_TRACK_JUSTIFICATION.value: SlideTypeInfo(
                name=SlideType.SCIENTIFIC_TRACK_JUSTIFICATION.value,
                description="this is a slide that explicitly justifies the scientific nature of the work or explains why the scientific track was chosen. It contains reasoning about the scientific contribution, research methodology, or academic value of the project.",
                category="content"
            )
        }
        
        for slide_type, info in default_types.items():
            self._slide_types[slide_type] = info
    
    def add_slide_type(self, name: str, description: str, category: str = "general", 
                      aliases: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a new slide type
        
        Args:
            name: Name of the slide type
            description: Description of what this slide type contains
            category: Category for grouping (e.g., "content", "structure", "technical")
            aliases: Alternative names for this slide type
            metadata: Additional metadata
            
        Returns:
            True if added successfully, False if already exists
        """
        if name in self._slide_types:
            return False
        
        self._slide_types[name] = SlideTypeInfo(
            name=name,
            description=description,
            category=category,
            aliases=aliases or [],
            metadata=metadata or {}
        )
        return True
    
    def remove_slide_type(self, name: str) -> bool:
        """Remove a slide type"""
        if name in self._slide_types:
            del self._slide_types[name]
            return True
        return False
    
    def get_slide_type_info(self, name: str) -> Optional[SlideTypeInfo]:
        """Get information about a slide type"""
        return self._slide_types.get(name)
    
    def get_all_slide_types(self) -> List[str]:
        """Get all slide type names"""
        return list(self._slide_types.keys())
    
    def get_slide_types_by_category(self, category: str) -> List[str]:
        """Get slide types by category"""
        return [name for name, info in self._slide_types.items() if info.category == category]
    
    def get_categories(self) -> Set[str]:
        """Get all available categories"""
        return {info.category for info in self._slide_types.values()}
    
    def validate_slide_type(self, name: str) -> bool:
        """Check if a slide type exists"""
        return name in self._slide_types
    
    def get_slide_types_with_aliases(self) -> Dict[str, List[str]]:
        """Get slide types with their aliases"""
        return {name: info.aliases for name, info in self._slide_types.items() if info.aliases}
    
    def find_slide_type_by_alias(self, alias: str) -> Optional[str]:
        """Find slide type by alias"""
        for name, info in self._slide_types.items():
            if alias in info.aliases:
                return name
        return None
    
    def export_to_json(self, filepath: Optional[str] = None) -> str:
        """Export slide types to JSON"""
        data = {
            name: {
                "description": info.description,
                "category": info.category,
                "aliases": info.aliases,
                "metadata": info.metadata
            }
            for name, info in self._slide_types.items()
        }
        
        json_str = json.dumps(data, indent=2)
        
        if filepath:
            Path(filepath).write_text(json_str)
        
        return json_str
    
    def import_from_json(self, json_str: str) -> int:
        """Import slide types from JSON, returns number of imported types"""
        data = json.loads(json_str)
        imported_count = 0
        
        for name, info_data in data.items():
            if self.add_slide_type(
                name=name,
                description=info_data["description"],
                category=info_data.get("category", "general"),
                aliases=info_data.get("aliases", []),
                metadata=info_data.get("metadata", {})
            ):
                imported_count += 1
        
        return imported_count
    
    def generate_slide_type_prompt_section(self) -> str:
        """
        Generate the slide type descriptions section for the prompt.
        This creates the numbered list of slide types with their descriptions.
        """
        prompt_sections = []
        
        for i, (name, info) in enumerate(self._slide_types.items(), 1):
            prompt_sections.append(f"{i}) {name} - {info.description}")
        
        return "\n\n".join(prompt_sections)
    
    def generate_slide_helper_type_prompt(self) -> str:
        """
        Generate the complete slide helper type prompt with dynamic slide type descriptions.
        
        Args:
            schema_format: Template variable for schema format
            description: Template variable for slide description
            
        Returns:
            Complete prompt with dynamic slide type descriptions
        """
        slide_types_section = self.generate_slide_type_prompt_section()
        
        prompt = f"""
You are an expert in detailed presentation analysis. You are provided with a single slide.
You need to analyze the slide and determine it's type and if it contains infographics.
DO NOT make assumptions and DO NOT invent anything regarding what might be on other slides.
You always work with only one slide.

You need to remember that slides can contain information of the following types and also belong to the corresponding sections:
{slide_types_section}

Return the answer as JSON strictly following the format instructions.

IMPORTANT! You cannot specify more than three types for one slide. But you can not specify any type if the slide does not belong to any of the listed types.
Infographics are:
- Numerical graphics (e.g., boxplots, circular and bar charts, graphs, tables with data),
- Diagrams, workflows, charts describing the approach / solution
IMPORTANT! Slide may contain some background images which are decorative and not a part of the slide content - they should be ignored
"""
        return prompt.strip()

# Global instance for easy access
slide_type_manager = SlideTypeManager()

# Convenience functions
def get_slide_types() -> List[str]:
    """Get all slide types"""
    return slide_type_manager.get_all_slide_types()

def add_slide_type(name: str, description: str, category: str = "general", 
                  aliases: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None) -> bool:
    """Add a new slide type"""
    return slide_type_manager.add_slide_type(name, description, category, aliases, metadata)

def get_slide_types_by_category(category: str) -> List[str]:
    """Get slide types by category"""
    return slide_type_manager.get_slide_types_by_category(category)

def validate_slide_type(name: str) -> bool:
    """Validate if a slide type exists"""
    return slide_type_manager.validate_slide_type(name)

def generate_slide_helper_type_prompt() -> str:
    """Generate the complete slide helper type prompt with dynamic slide type descriptions"""
    return slide_type_manager.generate_slide_helper_type_prompt()

def get_slide_type_prompt_section() -> str:
    """Get the slide type descriptions section for prompts"""
    return slide_type_manager.generate_slide_type_prompt_section()
