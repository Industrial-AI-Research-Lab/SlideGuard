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
        """Load default slide types"""
        default_types = {
            SlideType.TITLE_SLIDE.value: SlideTypeInfo(
                name=SlideType.TITLE_SLIDE.value,
                description="First slide with presentation title and presenter information",
                category="structure"
            ),
            SlideType.SEPARATOR.value: SlideTypeInfo(
                name=SlideType.SEPARATOR.value,
                description="Slide that separates logical sections of the presentation",
                category="structure"
            ),
            SlideType.MOTIVATION.value: SlideTypeInfo(
                name=SlideType.MOTIVATION.value,
                description="Slide containing project motivation and problem statement",
                category="content"
            ),
            SlideType.GOAL.value: SlideTypeInfo(
                name=SlideType.GOAL.value,
                description="Slide with explicitly formulated goals for the project",
                category="content"
            ),
            SlideType.TASKS.value: SlideTypeInfo(
                name=SlideType.TASKS.value,
                description="Slide describing tasks needed to implement the project",
                category="content"
            ),
            SlideType.CURRENT_STATE.value: SlideTypeInfo(
                name=SlideType.CURRENT_STATE.value,
                description="Slide about current state of the field and existing solutions",
                category="content"
            ),
            SlideType.PROPOSED_SOLUTION.value: SlideTypeInfo(
                name=SlideType.PROPOSED_SOLUTION.value,
                description="Slide with proposed solution workflow or diagram",
                category="content"
            ),
            SlideType.EXPERIMENT_SETTINGS.value: SlideTypeInfo(
                name=SlideType.EXPERIMENT_SETTINGS.value,
                description="Slide with experiment datasets and hyperparameters",
                category="technical"
            ),
            SlideType.EXPERIMENTAL_RESULTS.value: SlideTypeInfo(
                name=SlideType.EXPERIMENTAL_RESULTS.value,
                description="Slide with experimental results showing solution effectiveness",
                category="content"
            ),
            SlideType.CONCLUSION.value: SlideTypeInfo(
                name=SlideType.CONCLUSION.value,
                description="Slide with presentation conclusion and summary",
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
