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

from slideguard.criteria.presentation_types import PresentationType

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
    SCIENTIFIC_NOVELTY = "Scientific Novelty"
    PUBLICATION_READINESS = "Publication Readiness"
    TECHNOLOGICAL_NOVELTY = "Technological Novelty"
    TECHNOLOGICAL_REALIZATION_LEVEL = "Technological Realization Level"
    INDUSTRIAL_POTENTIAL = "Industrial Potential"
    COLLABORATIVE_PROGRESS = "Collaborative Progress"

@dataclass
class SlideTypeInfo:
    """Information about a slide type"""
    name: str
    description: str
    category: str = "general"
    aliases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    presentation_type: Optional[PresentationType] = None  # If None, applies to all presentation types

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
            SlideType.SCIENTIFIC_NOVELTY.value: SlideTypeInfo(
                name=SlideType.SCIENTIFIC_NOVELTY.value,
                description="this is a slide that explains what makes the project unique by detailing how its approach differs from known solutions, outlining the proposed new data, methods, or models, specifying which gaps in the field it closes, and stating its potential scientific or practical consequences.",
                category="content",
                presentation_type=PresentationType.SCIENTIFIC  
            ),
            SlideType.PUBLICATION_READINESS.value: SlideTypeInfo(
                name=SlideType.PUBLICATION_READINESS.value,
                description="this is a slide that demonstrates readiness for academic publication, indicating the status of preprints, drafts, or abstracts; identifying target journals or conferences; and noting any preliminary reviews or revised manuscript versions.",
                category="content",
                presentation_type=PresentationType.SCIENTIFIC  
            ),
            SlideType.TECHNOLOGICAL_NOVELTY.value: SlideTypeInfo(
                name=SlideType.TECHNOLOGICAL_NOVELTY.value,
                description="this is a slide that describes how the project differs from existing solutions, highlighting the new technological principles or approaches it implements and the concrete practical advantage this provides.",
                category="content",
                presentation_type=PresentationType.TECHNOLOGICAL
            ),
            SlideType.TECHNOLOGICAL_REALIZATION_LEVEL.value: SlideTypeInfo(
                name=SlideType.TECHNOLOGICAL_REALIZATION_LEVEL.value,
                description="this is a slide that defines the project's maturity by detailing the system architecture and components, the specific technologies, APIs, and equipment used, and presenting metrics for performance and scalability.",
                category="content",
                presentation_type=PresentationType.TECHNOLOGICAL
            ),
            SlideType.INDUSTRIAL_POTENTIAL.value: SlideTypeInfo(
                name=SlideType.INDUSTRIAL_POTENTIAL.value,
                description="this is a slide that specifies where and how the project can be implemented in industry, outlining its expected economic benefits and technological impact.",
                category="content",
                presentation_type=PresentationType.INDUSTRIAL
            ),
            SlideType.COLLABORATIVE_PROGRESS.value: SlideTypeInfo(
                name=SlideType.COLLABORATIVE_PROGRESS.value,
                description="this is a slide that summarizes team progress, listing completed stages, current ongoing work, and describing the communication flow within the team and with any external clients or partners.",
                category="content",
                presentation_type=PresentationType.COLLABORATIVE
            ),
            SlideType.SCIENTIFIC_TRACK_JUSTIFICATION.value: SlideTypeInfo(
                name=SlideType.SCIENTIFIC_TRACK_JUSTIFICATION.value,
                description="this is a slide that explicitly justifies the scientific nature of the work or explains why the scientific track was chosen. It contains reasoning about the scientific contribution, research methodology, or academic value of the project.",
                category="content",
                presentation_type=PresentationType.SCIENTIFIC
            )
        }
        
        for slide_type, info in default_types.items():
            self._slide_types[slide_type] = info
    
    def add_slide_type(self, name: str, description: str, category: str = "general", 
                      aliases: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None,
                      presentation_type: Optional[PresentationType] = None) -> bool:
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
            metadata=metadata or {},
            presentation_type=presentation_type
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
    
    def get_slide_types_for_presentation_type(self, presentation_type: Optional[PresentationType] = None) -> List[str]:
        """
        Get slide types filtered by presentation type.
        If presentation_type is None, returns all slide types.
        
        Args:
            presentation_type: The presentation type to filter by, or None for all types
            
        Returns:
            List of slide type names that are applicable to the given presentation type
        """
        if presentation_type is None:
            return self.get_all_slide_types()
        
        result = []
        for name, info in self._slide_types.items():
            # Include slide types that are not restricted to a specific presentation type
            # or are specifically for this presentation type
            if info.presentation_type is None or info.presentation_type == presentation_type:
                result.append(name)
        return result
    
    def generate_slide_type_prompt_section(self, presentation_type: Optional[PresentationType] = None) -> str:
        """
        Generate the slide type descriptions section for the prompt.
        This creates the numbered list of slide types with their descriptions.
        """
        prompt_sections = [
            f"{name} - {info.description}"
            for name, info in self._slide_types.items()
            if info.presentation_type in (None, presentation_type)
        ]
        return "\n\n".join(f"{i}) {text}" for i, text in enumerate(prompt_sections, 1))
    
    def generate_slide_helper_type_prompt(self, presentation_type: Optional[PresentationType] = None) -> str:
        """
        Generate the complete slide helper type prompt with dynamic slide type descriptions.
        
        Args:
            schema_format: Template variable for schema format
            description: Template variable for slide description
            
        Returns:
            Complete prompt with dynamic slide type descriptions
        """
        slide_types_section = self.generate_slide_type_prompt_section(presentation_type=presentation_type)
        
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
                  aliases: Optional[List[str]] = None, metadata: Optional[Dict[str, Any]] = None,
                  presentation_type: Optional[PresentationType] = None) -> bool:
    """Add a new slide type"""
    return slide_type_manager.add_slide_type(name, description, category, aliases, metadata, presentation_type)

def get_slide_types_for_presentation_type(presentation_type: Optional[PresentationType] = None) -> List[str]:
    """Get slide types filtered by presentation type"""
    return slide_type_manager.get_slide_types_for_presentation_type(presentation_type)

def get_slide_types_by_category(category: str) -> List[str]:
    """Get slide types by category"""
    return slide_type_manager.get_slide_types_by_category(category)

def validate_slide_type(name: str) -> bool:
    """Validate if a slide type exists"""
    return slide_type_manager.validate_slide_type(name)

def generate_slide_helper_type_prompt(presentation_type: Optional[PresentationType] = None) -> str:
    """Generate the complete slide helper type prompt with dynamic slide type descriptions"""
    return slide_type_manager.generate_slide_helper_type_prompt(presentation_type=presentation_type)

def get_slide_type_prompt_section(presentation_type: Optional[PresentationType] = None) -> str:
    """Get the slide type descriptions section for prompts"""
    return slide_type_manager.generate_slide_type_prompt_section(presentation_type=presentation_type)
