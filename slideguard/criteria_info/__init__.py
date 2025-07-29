from typing import Dict, List, Optional
from .base import CriterionInfo
from .slide_helper_description import slide_helper_description
from .slide_visual_arrangement import slide_visual_arrangement
from .deck_structure_analysis import deck_structure_analysis

# Separate registries for different criterion types
_SLIDE_CRITERIA_REGISTRY: Dict[str, CriterionInfo] = {}
_DECK_CRITERIA_REGISTRY: Dict[str, CriterionInfo] = {}

# Combined registry for backward compatibility
_CRITERIA_REGISTRY: Dict[str, CriterionInfo] = {}

def _register_criterion(criterion: CriterionInfo) -> None:
    """Internal function to register a criterion in the appropriate registry."""
    if criterion.criterion_type == "slide":
        _SLIDE_CRITERIA_REGISTRY[criterion.criterion_name] = criterion
    elif criterion.criterion_type == "deck":
        _DECK_CRITERIA_REGISTRY[criterion.criterion_name] = criterion
    
    # Also add to combined registry for backward compatibility
    _CRITERIA_REGISTRY[criterion.criterion_name] = criterion

# Register existing criteria
_register_criterion(slide_helper_description)
_register_criterion(slide_visual_arrangement)
_register_criterion(deck_structure_analysis)

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

def register_criterion(criterion: CriterionInfo) -> None:
    """
    Register a new criterion.
    
    Args:
        criterion: The CriterionInfo object to register
    """
    _CRITERIA_REGISTRY[criterion.criterion_name] = criterion

def unregister_criterion(criterion_name: str) -> bool:
    """
    Remove a criterion from the registry.
    
    Args:
        criterion_name: The name of the criterion to remove
        
    Returns:
        True if criterion was removed, False if not found
    """
    if criterion_name in _CRITERIA_REGISTRY:
        del _CRITERIA_REGISTRY[criterion_name]
        return True
    return False

# Convenience access to commonly used criteria
slide_description = slide_helper_description
slide_visual_arrangement = slide_visual_arrangement
deck_structure = deck_structure_analysis
