"""
Example usage of SlideGuard crew-based evaluation system
"""

import sys
import os
import asyncio

# Add the project root to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from slideguard.crew.evaluator import SlideGuardEvaluator, evaluate_presentation_sync
from slideguard.criteria import get_available_criteria, get_criteria_by_category
from slideguard.config import config

def example_basic_evaluation():
    """Example of basic presentation evaluation"""
    print("=== Basic Presentation Evaluation ===")
    
    # Initialize evaluator (will use environment variables if set)
    evaluator = SlideGuardEvaluator()
    
    # Check if LLM is available
    if evaluator.llm is None:
        print("LLM not available. Set environment variables:")
        print("export SLIDEGUARD_LLM_API_KEY='your-api-key'")
        print("export SLIDEGUARD_LLM_API_BASE='http://localhost:8000/v1'")
        return
    
    print("Basic evaluation would use all available criteria")
    print(f"Available criteria: {get_available_criteria()}")

async def example_async_evaluation():
    """Example of async evaluation"""
    print("\n=== Async Evaluation Example ===")
    
    evaluator = SlideGuardEvaluator()
    
    if evaluator.llm is None:
        print("LLM not available. Set environment variables.")
        return
    
    try:
        # Basic evaluation
        result = await evaluator.evaluate_presentation("presentation.pdf")
        print(f"Overall score: {result.overall_score}")
        print(f"Summary: {result.summary}")
        
    except Exception as e:
        print(f"Evaluation failed: {e}")

def example_filtered_evaluation():
    """Example of evaluation with specific criteria and slide type filtering"""
    print("\n=== Filtered Evaluation ===")
    
    # Example with specific criteria
    slide_criteria = ["Slide Visual Arrangement", "Slide Color Analysis"]
    deck_criteria = ["Deck Structure Analysis"]
    
    # Example with slide type filtering
    slide_types_filter = ["goals", "experimental_results"]
    
    print(f"Slide criteria: {slide_criteria}")
    print(f"Deck criteria: {deck_criteria}")
    print(f"Slide types filter: {slide_types_filter}")
    
    # Note: This would require an LLM instance to actually run
    print("Note: This example shows the configuration but would need an LLM to execute")

async def example_category_based_evaluation():
    """Example of evaluation using criteria by category"""
    print("\n=== Category-Based Evaluation ===")
    
    evaluator = SlideGuardEvaluator()
    
    if evaluator.llm is None:
        print("LLM not available. Set environment variables.")
        return
    
    try:
        # Get criteria by category
        visual_criteria = get_criteria_by_category("visual")
        content_criteria = get_criteria_by_category("content")
        structure_criteria = get_criteria_by_category("structure")
        
        print(f"Visual criteria: {[c.criterion_name for c in visual_criteria]}")
        print(f"Content criteria: {[c.criterion_name for c in content_criteria]}")
        print(f"Structure criteria: {[c.criterion_name for c in structure_criteria]}")
        
        # Example: Evaluate only visual aspects
        visual_criterion_names = [c.criterion_name for c in visual_criteria]
        
        result = await evaluator.evaluate_presentation(
            "presentation.pdf",
            slide_criteria=visual_criterion_names
        )
        
        print(f"Visual evaluation score: {result.overall_score}")
        
    except Exception as e:
        print(f"Category-based evaluation failed: {e}")

def example_custom_criteria():
    """Example of how to create and use custom criteria"""
    print("\n=== Custom Criteria Example ===")
    
    from slideguard.criteria.base import CriterionInfo
    from pydantic import BaseModel, Field
    
    # Define custom criterion schema
    class CustomAnalysisResult(BaseModel):
        custom_score: int = Field(description="Custom score from 1 to 10", ge=1, le=10)
        custom_feedback: str = Field(description="Custom feedback")
        recommendations: list[str] = Field(description="Custom recommendations")
    
    # Create custom criterion
    custom_criterion = CriterionInfo(
        criterion_name="Custom Analysis",
        criterion_type="slide",
        criterion_description="Custom analysis for specific needs",
        criterion_prompt="Analyze the slide according to custom requirements...",
        criterion_schema=CustomAnalysisResult,
        applicable_slide_types=["goals", "conclusion"],  # Only for specific slide types
        priority=5,
        requires_slide_type=True,
        category="custom"
    )
    
    print(f"Custom criterion created: {custom_criterion.criterion_name}")
    print(f"Applicable to slide types: {custom_criterion.applicable_slide_types}")

def example_environment_setup():
    """Example of how to set up environment variables"""
    print("\n=== Environment Setup Example ===")
    
    # Show current configuration status
    config.print_config_status()
    
    print("\nTo configure, you can:")
    print("1. Set environment variables manually:")
    print("   export SLIDEGUARD_LLM_API_KEY='your-api-key'")
    print("   export SLIDEGUARD_LLM_API_BASE='http://localhost:8000/v1'")
    print("   export SLIDEGUARD_LLM_MODEL='/model'")
    print()
    print("2. Use the setup script:")
    print("   python -m slideguard.setup setup")
    print()
    print("3. Create a .env file manually")

async def main():
    """Main function demonstrating various usage patterns"""
    print("SlideGuard Crew-Based Evaluation System Examples")
    print("=" * 60)
    
    # Show available criteria
    available_criteria = get_available_criteria()
    print(f"Available slide criteria: {len(available_criteria['slide'])}")
    print(f"Available deck criteria: {len(available_criteria['deck'])}")
    
    # Show environment setup
    example_environment_setup()
    
    # Run examples
    example_basic_evaluation()
    await example_async_evaluation()
    example_filtered_evaluation()
    await example_category_based_evaluation()
    example_custom_criteria()
    
    print("\n" + "=" * 60)
    print("Examples completed!")
    print("\nTo run actual evaluations:")
    print("1. Set up your environment variables")
    print("2. Install required dependencies: pip install crewai openai python-dotenv")
    print("3. Run: python -m slideguard.setup test")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main()) 