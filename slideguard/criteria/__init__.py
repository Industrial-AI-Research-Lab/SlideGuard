from typing import Dict, List, Optional
from .base import CriterionInfo, SLIDE_TYPES, CRITERION_CATEGORIES
from .slide_helper_description import slide_helper_description
from .slide_visual_arrangement import slide_visual_arrangement
from .deck_structure_analysis import deck_structure_analysis
from .slide_helper_type import slide_helper_type
from .slide_color_analysis import slide_color_analysis
from .slide_content_quality import slide_content_quality
from .deck_storytelling import deck_storytelling

# Separate registries for different criterion types
_SLIDE_CRITERIA_REGISTRY: Dict[str, CriterionInfo] = {}
_DECK_CRITERIA_REGISTRY: Dict[str, CriterionInfo] = {}

# Registry organized by category
_CRITERIA_BY_CATEGORY: Dict[str, List[CriterionInfo]] = {}

# Combined registry for backward compatibility
_CRITERIA_REGISTRY: Dict[str, CriterionInfo] = {}

def _register_criterion(criterion: CriterionInfo) -> None:
    """Internal function to register a criterion in the appropriate registry."""
    if criterion.criterion_type == "slide":
        _SLIDE_CRITERIA_REGISTRY[criterion.criterion_name] = criterion
    elif criterion.criterion_type == "deck":
        _DECK_CRITERIA_REGISTRY[criterion.criterion_name] = criterion
    
    # Add to combined registry for backward compatibility
    _CRITERIA_REGISTRY[criterion.criterion_name] = criterion
    
    # Add to category registry
    category = criterion.category
    if category not in _CRITERIA_BY_CATEGORY:
        _CRITERIA_BY_CATEGORY[category] = []
    _CRITERIA_BY_CATEGORY[category].append(criterion)

# Register existing criteria
_register_criterion(slide_helper_description)
_register_criterion(slide_visual_arrangement)
_register_criterion(deck_structure_analysis)
_register_criterion(slide_helper_type)
_register_criterion(slide_color_analysis)
_register_criterion(slide_content_quality)
_register_criterion(deck_storytelling)

def get_criterion(criterion_name: str) -> Optional[CriterionInfo]:
    """
    Get a specific criterion by name.
    
    Args:
        criterion_name: The name of the criterion to retrieve
        
    Returns:
        The CriterionInfo object if found, None otherwise
    """
    return _CRITERIA_REGISTRY.get(criterion_name)

def get_all_criteria() -> List[CriterionInfo]:
    """
    Get all available criteria.
    
    Returns:
        List of all CriterionInfo objects
    """
    return list(_CRITERIA_REGISTRY.values())

def get_criterion_names() -> List[str]:
    """
    Get names of all available criteria.
    
    Returns:
        List of criterion names
    """
    return list(_CRITERIA_REGISTRY.keys())

def get_slide_criteria() -> List[CriterionInfo]:
    """
    Get all slide-level criteria.
    
    Returns:
        List of slide CriterionInfo objects
    """
    return list(_SLIDE_CRITERIA_REGISTRY.values())

def get_deck_criteria() -> List[CriterionInfo]:
    """
    Get all deck-level criteria.
    
    Returns:
        List of deck CriterionInfo objects
    """
    return list(_DECK_CRITERIA_REGISTRY.values())

def get_slide_criterion_names() -> List[str]:
    """
    Get names of all slide-level criteria.
    
    Returns:
        List of slide criterion names
    """
    return list(_SLIDE_CRITERIA_REGISTRY.keys())

def get_deck_criterion_names() -> List[str]:
    """
    Get names of all deck-level criteria.
    
    Returns:
        List of deck criterion names
    """
    return list(_DECK_CRITERIA_REGISTRY.keys())

def get_criteria_by_type(criterion_type: str) -> List[CriterionInfo]:
    """
    Get criteria by type (slide or deck).
    
    Args:
        criterion_type: Either "slide" or "deck"
        
    Returns:
        List of CriterionInfo objects of the specified type
    """
    if criterion_type == "slide":
        return get_slide_criteria()
    elif criterion_type == "deck":
        return get_deck_criteria()
    else:
        raise ValueError(f"Invalid criterion_type: {criterion_type}. Must be 'slide' or 'deck'")

def get_criterion_names_by_type(criterion_type: str) -> List[str]:
    """
    Get criterion names by type (slide or deck).
    
    Args:
        criterion_type: Either "slide" or "deck"
        
    Returns:
        List of criterion names of the specified type
    """
    if criterion_type == "slide":
        return get_slide_criterion_names()
    elif criterion_type == "deck":
        return get_deck_criterion_names()
    else:
        raise ValueError(f"Invalid criterion_type: {criterion_type}. Must be 'slide' or 'deck'")

def get_criteria_by_category(category: str) -> List[CriterionInfo]:
    """
    Get criteria by category.
    
    Args:
        category: Category name (e.g., "visual", "content", "structure")
        
    Returns:
        List of CriterionInfo objects in the specified category
    """
    return _CRITERIA_BY_CATEGORY.get(category, [])

def get_criteria_by_slide_type(slide_type: str) -> List[CriterionInfo]:
    """
    Get criteria that are applicable to a specific slide type.
    
    Args:
        slide_type: The slide type to filter by
        
    Returns:
        List of CriterionInfo objects applicable to the slide type
    """
    applicable_criteria = []
    for criterion in get_all_criteria():
        if (criterion.applicable_slide_types is None or 
            slide_type in criterion.applicable_slide_types):
            applicable_criteria.append(criterion)
    return applicable_criteria

def get_criteria_for_slide_types(slide_types: List[str]) -> List[CriterionInfo]:
    """
    Get criteria that are applicable to any of the specified slide types.
    
    Args:
        slide_types: List of slide types to filter by
        
    Returns:
        List of CriterionInfo objects applicable to any of the slide types
    """
    applicable_criteria = []
    for criterion in get_all_criteria():
        if (criterion.applicable_slide_types is None or 
            any(st in criterion.applicable_slide_types for st in slide_types)):
            applicable_criteria.append(criterion)
    return applicable_criteria

def get_criteria_sorted_by_priority(criterion_type: str = None) -> List[CriterionInfo]:
    """
    Get criteria sorted by priority (lower number = higher priority).
    
    Args:
        criterion_type: Optional filter by criterion type ("slide" or "deck")
        
    Returns:
        List of CriterionInfo objects sorted by priority
    """
    if criterion_type:
        criteria = get_criteria_by_type(criterion_type)
    else:
        criteria = get_all_criteria()
    
    return sorted(criteria, key=lambda x: x.priority)

def register_criterion(criterion: CriterionInfo) -> None:
    """
    Register a new criterion.
    
    Args:
        criterion: The CriterionInfo object to register
    """
    _register_criterion(criterion)

def unregister_criterion(criterion_name: str) -> bool:
    """
    Remove a criterion from the registry.
    
    Args:
        criterion_name: The name of the criterion to remove
        
    Returns:
        True if criterion was removed, False if not found
    """
    if criterion_name in _CRITERIA_REGISTRY:
        criterion = _CRITERIA_REGISTRY[criterion_name]
        
        # Remove from type-specific registry
        if criterion.criterion_type == "slide":
            del _SLIDE_CRITERIA_REGISTRY[criterion_name]
        elif criterion.criterion_type == "deck":
            del _DECK_CRITERIA_REGISTRY[criterion_name]
        
        # Remove from category registry
        category = criterion.category
        if category in _CRITERIA_BY_CATEGORY:
            _CRITERIA_BY_CATEGORY[category] = [
                c for c in _CRITERIA_BY_CATEGORY[category] 
                if c.criterion_name != criterion_name
            ]
        
        # Remove from combined registry
        del _CRITERIA_REGISTRY[criterion_name]
        return True
    return False

def get_available_categories() -> List[str]:
    """
    Get all available criterion categories.
    
    Returns:
        List of category names
    """
    return list(_CRITERIA_BY_CATEGORY.keys())

def get_available_slide_types() -> List[str]:
    """
    Get all available slide types.
    
    Returns:
        List of slide type names
    """
    return SLIDE_TYPES.copy()

def get_available_criteria() -> Dict[str, List[str]]:
    """
    Get all available criteria organized by type.
    
    Returns:
        Dictionary with 'slide' and 'deck' keys containing lists of criterion names
    """
    return {
        "slide": [c.criterion_name for c in get_slide_criteria()],
        "deck": [c.criterion_name for c in get_deck_criteria()]
    }

# Convenience access to commonly used criteria
slide_description = slide_helper_description
slide_visual_arrangement = slide_visual_arrangement
deck_structure = deck_structure_analysis
slide_type = slide_helper_type
slide_color = slide_color_analysis
slide_content = slide_content_quality
