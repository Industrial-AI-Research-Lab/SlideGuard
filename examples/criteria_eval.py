"""
Example usage of SlideGuard crew-based evaluation system
"""

import asyncio
import os
from slideguard.crew.evaluator import SlideGuardEvaluator, evaluate_presentation_sync
from slideguard.criteria import get_criteria_by_category

async def example_async_evaluation():
    """Example of async evaluation using environment variables"""
    print("=== Async Evaluation Example ===")
    
    # Initialize evaluator (will use environment variables if set)
    evaluator = SlideGuardEvaluator()
    
    # Check if LLM is available
    if evaluator.llm is None:
        print("LLM not available. Set environment variables:")
        print("export SLIDEGUARD_LLM_API_KEY='your-api-key'")
        print("export SLIDEGUARD_LLM_API_BASE='http://localhost:8000/v1'")
        return
    
    try:
        # Basic evaluation
        result = await evaluator.evaluate_presentation("presentation.pdf")
        print(f"Overall score: {result.overall_score}")
        print(f"Summary: {result.summary}")
        
    except Exception as e:
        print(f"Evaluation failed: {e}")

def example_sync_evaluation():
    """Example of synchronous evaluation"""
    print("\n=== Synchronous Evaluation Example ===")
    
    try:
        # Synchronous evaluation
        result = evaluate_presentation_sync("presentation.pdf")
        print(f"Overall score: {result.overall_score}")
        print(f"Summary: {result.summary}")
        
    except Exception as e:
        print(f"Evaluation failed: {e}")

async def example_filtered_evaluation():
    """Example of filtered evaluation"""
    print("\n=== Filtered Evaluation Example ===")
    
    evaluator = SlideGuardEvaluator()
    
    if evaluator.llm is None:
        print("LLM not available. Set environment variables.")
        return
    
    try:
        # Filtered evaluation with specific criteria and slide types
        result = await evaluator.evaluate_presentation(
            "presentation.pdf",
            slide_criteria=["Slide Visual Arrangement", "Slide Color Analysis"],
            deck_criteria=["Deck Structure Analysis"],
            slide_types_filter=["goals", "experimental_results"]
        )
        
        print(f"Filtered evaluation score: {result.overall_score}")
        
    except Exception as e:
        print(f"Filtered evaluation failed: {e}")

async def example_category_based_evaluation():
    """Example of category-based evaluation"""
    print("\n=== Category-Based Evaluation Example ===")
    
    evaluator = SlideGuardEvaluator()
    
    if evaluator.llm is None:
        print("LLM not available. Set environment variables.")
        return
    
    try:
        # Get criteria by category
        visual_criteria = get_criteria_by_category("visual")
        visual_criterion_names = [c.criterion_name for c in visual_criteria]
        
        # Evaluate only visual aspects
        result = await evaluator.evaluate_presentation(
            "presentation.pdf",
            slide_criteria=visual_criterion_names
        )
        
        print(f"Visual evaluation score: {result.overall_score}")
        
    except Exception as e:
        print(f"Category-based evaluation failed: {e}")

def example_environment_setup():
    """Example of how to set up environment variables"""
    print("\n=== Environment Setup Example ===")
    print("To use the evaluation system, set these environment variables:")
    print()
    print("# For vLLM server:")
    print("export SLIDEGUARD_LLM_API_KEY='your-api-key'")
    print("export SLIDEGUARD_LLM_API_BASE='http://localhost:8000/v1'")
    print()
    print("# Or for other OpenAI-compatible services:")
    print("export SLIDEGUARD_LLM_API_KEY='your-openai-key'")
    print("export SLIDEGUARD_LLM_API_BASE='https://api.openai.com/v1'")
    print()
    print("# Check current environment:")
    api_key = os.getenv('SLIDEGUARD_LLM_API_KEY')
    api_base = os.getenv('SLIDEGUARD_LLM_API_BASE')
    print(f"API Key set: {'Yes' if api_key else 'No'}")
    print(f"API Base set: {'Yes' if api_base else 'No'}")

async def main():
    """Main function demonstrating various usage patterns"""
    print("SlideGuard Crew-Based Evaluation System Examples")
    print("=" * 60)
    
    # Show environment setup
    example_environment_setup()
    
    # Run examples
    await example_async_evaluation()
    example_sync_evaluation()
    await example_filtered_evaluation()
    await example_category_based_evaluation()
    
    print("\n" + "=" * 60)
    print("Examples completed!")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())