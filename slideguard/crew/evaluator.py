"""
Main evaluator for slide deck analysis using CrewAI agents
"""

import asyncio
import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from slideguard.crew.agents import SlideGuardAgents, DeckEvaluationResult
from slideguard.utils.file_manager import FileManager
from slideguard.utils.cache_manager import CacheManager
from slideguard.criteria import (
    get_slide_criteria, 
    get_deck_criteria, 
    get_criterion,
    CriterionInfo
)
from slideguard.config import config

def create_llm_from_env():
    """
    Create LLM instance from environment variables.
    
    Environment variables:
    - SLIDEGUARD_LLM_API_KEY: API key for the LLM service
    - SLIDEGUARD_LLM_API_BASE: Base URL for the LLM API (e.g., http://localhost:8000/v1)
    - SLIDEGUARD_LLM_MODEL: Model name (defaults to '/model')
    
    Returns:
        LLM instance or None if environment variables are not set
    """
    if not config.is_configured():
        print("Warning: LLM environment variables not set")
        print("Set SLIDEGUARD_LLM_API_KEY and SLIDEGUARD_LLM_API_BASE to enable full evaluation")
        return None
    
    try:
        # Try to import OpenAI client for vLLM compatibility
        from openai import OpenAI
        
        # Create OpenAI client configured for vLLM
        client = OpenAI(
            api_key=config.api_key,
            base_url=config.api_base
        )
        
        # For CrewAI, we need to create a compatible LLM wrapper
        # This is a simplified approach - you might need to adjust based on your specific setup
        return client
        
    except ImportError:
        print("Warning: openai package not installed. Install with: pip install openai")
        return None
    except Exception as e:
        print(f"Error creating LLM instance: {e}")
        return None

class SlideGuardEvaluator:
    """
    Main evaluator class for comprehensive slide deck analysis.
    
    This class provides a high-level interface for evaluating presentations
    using a crew of specialized AI agents that work together to analyze
    different aspects of slide decks.
    """
    
    def __init__(self, 
                 llm=None,
                 cache_dir: str = None,
                 file_cache_dir: str = None,
                 auto_init_llm: bool = True):
        """
        Initialize the SlideGuard evaluator.
        
        Args:
            llm: Language model instance (e.g., OpenAI client, GigaChat)
            cache_dir: Directory for caching evaluation results (uses config if None)
            file_cache_dir: Directory for caching file processing results (uses config if None)
            auto_init_llm: If True and no LLM provided, try to initialize from environment variables
        """
        # Use config values if not provided
        self.cache_dir = Path(cache_dir or config.cache_dir)
        self.file_cache_dir = Path(file_cache_dir or config.file_cache_dir)
        
        # Initialize LLM
        if llm is None and auto_init_llm:
            self.llm = create_llm_from_env()
        else:
            self.llm = llm
        
        # Initialize managers
        self.file_manager = FileManager(
            cache_dir=str(self.file_cache_dir),
            llm=self.llm
        )
        self.cache_manager = CacheManager(self.cache_dir)
        
        # Initialize agents
        self.agents = SlideGuardAgents(
            file_manager=self.file_manager,
            cache_manager=self.cache_manager,
            llm=self.llm
        )
    
    def print_status(self):
        """Print current evaluator status"""
        print("SlideGuard Evaluator Status:")
        print(f"  LLM Available: {'✓ Yes' if self.llm else '✗ No'}")
        print(f"  Cache Directory: {self.cache_dir}")
        print(f"  File Cache Directory: {self.file_cache_dir}")
        
        if self.llm is None:
            config.print_config_status()
    
    async def evaluate_presentation(self,
                                  presentation_path: str,
                                  slide_criteria: Optional[List[str]] = None,
                                  deck_criteria: Optional[List[str]] = None,
                                  slide_types_filter: Optional[List[str]] = None) -> DeckEvaluationResult:
        """
        Evaluate a presentation using the crew of agents.
        
        Args:
            presentation_path: Path to the presentation file (PDF)
            slide_criteria: List of slide-level criteria names to apply. If None, uses all available.
            deck_criteria: List of deck-level criteria names to apply. If None, uses all available.
            slide_types_filter: Optional filter for specific slide types to evaluate
            
        Returns:
            DeckEvaluationResult containing comprehensive evaluation results
        """
        
        # Validate presentation file
        if not Path(presentation_path).exists():
            raise FileNotFoundError(f"Presentation file not found: {presentation_path}")
        
        # Check if LLM is available
        if self.llm is None:
            raise ValueError("LLM instance is required for evaluation. Set environment variables or provide LLM instance.")
        
        # Get criteria based on names
        slide_criteria_objects = self._get_criteria_by_names(slide_criteria, "slide")
        deck_criteria_objects = self._get_criteria_by_names(deck_criteria, "deck")
        
        # Check cache for existing results
        cache_key = self._generate_cache_key(
            presentation_path, 
            slide_criteria, 
            deck_criteria, 
            slide_types_filter
        )
        
        cached_result = await self.cache_manager.get(
            cache_key, 
            Path(presentation_path).name, 
            "evaluation"
        )
        
        if cached_result:
            print(f"Using cached evaluation results for {presentation_path}")
            return DeckEvaluationResult(**cached_result)
        
        # Perform evaluation
        print(f"Starting evaluation of {presentation_path}")
        result = await self.agents.evaluate_presentation(
            presentation_path=presentation_path,
            slide_criteria=slide_criteria_objects,
            deck_criteria=deck_criteria_objects
        )
        
        # Apply slide type filter if specified
        if slide_types_filter:
            result = self._filter_by_slide_types(result, slide_types_filter)
        
        # Cache the result
        await self.cache_manager.put(
            cache_key,
            result.dict(),
            Path(presentation_path).name,
            "evaluation"
        )
        
        return result
    
    async def evaluate_slide(self,
                           slide_image_path: str,
                           slide_id: str,
                           criteria: Optional[List[str]] = None) -> Any:
        """
        Evaluate a single slide image.
        
        Args:
            slide_image_path: Path to the slide image file
            slide_id: Unique identifier for the slide
            criteria: List of criteria names to apply. If None, uses all slide criteria.
            
        Returns:
            SlideEvaluationResult for the slide
        """
        
        if self.llm is None:
            raise ValueError("LLM instance is required for evaluation. Set environment variables or provide LLM instance.")
        
        slide_criteria = self._get_criteria_by_names(criteria, "slide")
        
        return await self.agents.evaluate_slide(
            slide_image_path=slide_image_path,
            slide_id=slide_id,
            slide_criteria=slide_criteria
        )
    
    async def evaluate_deck_structure(self,
                                    slide_descriptions: List[str],
                                    criteria: Optional[List[str]] = None) -> List[Any]:
        """
        Evaluate deck structure using slide descriptions.
        
        Args:
            slide_descriptions: List of slide descriptions
            criteria: List of deck criteria names to apply. If None, uses all deck criteria.
            
        Returns:
            List of EvaluationResult objects
        """
        
        if self.llm is None:
            raise ValueError("LLM instance is required for evaluation. Set environment variables or provide LLM instance.")
        
        deck_criteria = self._get_criteria_by_names(criteria, "deck")
        
        return await self.agents.evaluate_deck(
            presentation_path="",  # Not used for deck-level evaluation
            slide_descriptions=slide_descriptions,
            deck_criteria=deck_criteria
        )
    
    def get_available_criteria(self) -> Dict[str, List[str]]:
        """
        Get all available criteria organized by type.
        
        Returns:
            Dictionary with 'slide' and 'deck' keys containing lists of criterion names
        """
        return {
            "slide": [c.criterion_name for c in get_slide_criteria()],
            "deck": [c.criterion_name for c in get_deck_criteria()]
        }
    
    def get_criterion_info(self, criterion_name: str) -> Optional[CriterionInfo]:
        """
        Get detailed information about a specific criterion.
        
        Args:
            criterion_name: Name of the criterion
            
        Returns:
            CriterionInfo object if found, None otherwise
        """
        return get_criterion(criterion_name)
    
    def _get_criteria_by_names(self, 
                              criterion_names: Optional[List[str]], 
                              criterion_type: str) -> List[CriterionInfo]:
        """Get criterion objects by names, falling back to all criteria of the type if None."""
        if criterion_names is None:
            if criterion_type == "slide":
                return get_slide_criteria()
            elif criterion_type == "deck":
                return get_deck_criteria()
            else:
                raise ValueError(f"Invalid criterion type: {criterion_type}")
        
        criteria = []
        for name in criterion_names:
            criterion = get_criterion(name)
            if criterion is None:
                print(f"Warning: Criterion '{name}' not found, skipping")
                continue
            if criterion.criterion_type != criterion_type:
                print(f"Warning: Criterion '{name}' is not a {criterion_type} criterion, skipping")
                continue
            criteria.append(criterion)
        
        return criteria
    
    def _generate_cache_key(self,
                           presentation_path: str,
                           slide_criteria: Optional[List[str]],
                           deck_criteria: Optional[List[str]],
                           slide_types_filter: Optional[List[str]]) -> str:
        """Generate a cache key for the evaluation parameters."""
        import hashlib
        
        # Create a string representation of the parameters
        params_str = f"{presentation_path}:{slide_criteria}:{deck_criteria}:{slide_types_filter}"
        
        # Generate hash
        return hashlib.md5(params_str.encode()).hexdigest()
    
    def _filter_by_slide_types(self, 
                              result: DeckEvaluationResult, 
                              slide_types: List[str]) -> DeckEvaluationResult:
        """Filter evaluation results to include only specified slide types."""
        
        # Filter slide evaluations
        filtered_slide_evaluations = []
        for slide_eval in result.slide_evaluations:
            # Check if any of the slide's types match the filter
            if any(slide_type in slide_eval.slide_type for slide_type in slide_types):
                filtered_slide_evaluations.append(slide_eval)
        
        # Create new result with filtered slides
        return DeckEvaluationResult(
            deck_name=result.deck_name,
            slide_evaluations=filtered_slide_evaluations,
            deck_evaluations=result.deck_evaluations,
            overall_score=result.overall_score,
            summary=result.summary
        )

# Convenience function for synchronous evaluation
def evaluate_presentation_sync(presentation_path: str,
                             llm=None,
                             slide_criteria: Optional[List[str]] = None,
                             deck_criteria: Optional[List[str]] = None,
                             slide_types_filter: Optional[List[str]] = None) -> DeckEvaluationResult:
    """
    Synchronous wrapper for presentation evaluation.
    
    Args:
        presentation_path: Path to the presentation file
        llm: Language model instance
        slide_criteria: List of slide criteria names
        deck_criteria: List of deck criteria names
        slide_types_filter: Optional filter for slide types
        
    Returns:
        DeckEvaluationResult
    """
    evaluator = SlideGuardEvaluator(llm=llm)
    
    async def _evaluate():
        return await evaluator.evaluate_presentation(
            presentation_path=presentation_path,
            slide_criteria=slide_criteria,
            deck_criteria=deck_criteria,
            slide_types_filter=slide_types_filter
        )
    
    return asyncio.run(_evaluate()) 