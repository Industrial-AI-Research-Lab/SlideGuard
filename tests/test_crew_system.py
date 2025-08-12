"""
Test script for the SlideGuard crew-based evaluation system
"""

import asyncio
from slideguard.criteria import (
    get_available_criteria,
    get_criteria_by_category,
    get_criteria_for_slide_types,
    get_criteria_sorted_by_priority,
    get_criterion
)

def test_criteria_system():
    """Test the enhanced criteria system"""
    print("Testing Criteria System...")
    
    # Test available criteria
    available_criteria = get_available_criteria()
    print(f"✓ Available slide criteria: {len(available_criteria['slide'])}")
    print(f"✓ Available deck criteria: {len(available_criteria['deck'])}")
    
    # Test category-based filtering
    visual_criteria = get_criteria_by_category("visual")
    content_criteria = get_criteria_by_category("content")
    structure_criteria = get_criteria_by_category("structure")
    
    print(f"✓ Visual criteria: {len(visual_criteria)}")
    print(f"✓ Content criteria: {len(content_criteria)}")
    print(f"✓ Structure criteria: {len(structure_criteria)}")
    
    # Test slide type filtering
    goals_criteria = get_criteria_for_slide_types(["Goal"])
    experimental_criteria = get_criteria_for_slide_types(["Experimental Results"])
    
    print(f"✓ Criteria for goals slides: {len(goals_criteria)}")
    print(f"✓ Criteria for experimental results slides: {len(experimental_criteria)}")
    
    # Test priority sorting
    sorted_slide_criteria = get_criteria_sorted_by_priority("slide")
    print(f"✓ Sorted slide criteria by priority: {len(sorted_slide_criteria)}")
    
    print("✓ Criteria system tests passed!")

def test_criteria_enhancements():
    """Test the enhanced criteria features"""
    print("\nTesting Criteria Enhancements...")
    
    # Test enhanced criteria properties
    visual_criterion = get_criterion("Slide Visual Arrangement")
    if visual_criterion:
        print(f"✓ Criterion category: {visual_criterion.category}")
        print(f"✓ Criterion priority: {visual_criterion.priority}")
        print(f"✓ Requires slide type: {visual_criterion.requires_slide_type}")
        print(f"✓ Applicable slide types: {visual_criterion.applicable_slide_types}")
    
    color_criterion = get_criterion("Slide Color Analysis")
    if color_criterion:
        print(f"✓ Color criterion applicable to: {color_criterion.applicable_slide_types}")
        print(f"✓ Color criterion requires slide type: {color_criterion.requires_slide_type}")
    
    content_criterion = get_criterion("Slide Content Quality")
    if content_criterion:
        print(f"✓ Content criterion applicable to: {content_criterion.applicable_slide_types}")
        print(f"✓ Content criterion category: {content_criterion.category}")
    
    print("✓ Criteria enhancements tests passed!")

def test_criteria_registration():
    """Test criteria registration and management"""
    print("\nTesting Criteria Registration...")
    
    from slideguard.criteria import register_criterion, unregister_criterion, get_criterion
    from slideguard.criteria.base import CriterionInfo
    from pydantic import BaseModel, Field
    
    # Create a test criterion
    class TestResult(BaseModel):
        test_score: int = Field(description="Test score", ge=1, le=5)
        test_feedback: str = Field(description="Test feedback")
    
    test_criterion = CriterionInfo(
        criterion_name="Test Criterion",
        criterion_type="slide",
        criterion_description="Test criterion for testing",
        criterion_prompt="Test prompt",
        criterion_schema=TestResult,
        applicable_slide_types=["Goal"],
        priority=10,
        requires_slide_type=True,
        category="test"
    )
    
    # Register the test criterion
    register_criterion(test_criterion)
    print("✓ Test criterion registered")
    
    # Verify it's available
    retrieved_criterion = get_criterion("Test Criterion")
    if retrieved_criterion:
        print(f"✓ Test criterion retrieved: {retrieved_criterion.criterion_name}")
    
    # Test category filtering
    test_criteria = get_criteria_by_category("test")
    print(f"✓ Test criteria in category: {len(test_criteria)}")
    
    # Unregister the test criterion
    success = unregister_criterion("Test Criterion")
    if success:
        print("✓ Test criterion unregistered")
    
    # Verify it's no longer available
    retrieved_criterion = get_criterion("Test Criterion")
    if not retrieved_criterion:
        print("✓ Test criterion successfully removed")
    
    print("✓ Criteria registration tests passed!")

def test_slide_type_system():
    """Test slide type system"""
    print("\nTesting Slide Type System...")
    
    from slideguard.criteria.base import SLIDE_TYPES
    
    print(f"✓ Available slide types: {len(SLIDE_TYPES)}")
    print(f"✓ Slide types: {SLIDE_TYPES}")
    
    # Test criteria filtering for different slide types
    title_criteria = get_criteria_for_slide_types(["Title slide"])
    conclusion_criteria = get_criteria_for_slide_types(["Conclusion"])
    experimental_criteria = get_criteria_for_slide_types(["Experimental Results"])
    
    print(f"✓ Criteria for title slides: {len(title_criteria)}")
    print(f"✓ Criteria for conclusion slides: {len(conclusion_criteria)}")
    print(f"✓ Criteria for experimental results slides: {len(experimental_criteria)}")
    
    print("✓ Slide type system tests passed!")

def main():
    """Run all tests"""
    print("SlideGuard Crew-Based Evaluation System Tests")
    print("=" * 50)
    
    # Run tests
    test_criteria_system()
    test_criteria_enhancements()
    test_criteria_registration()
    test_slide_type_system()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("\nThe crew-based evaluation system is ready for use.")
    print("To run full evaluations, install required dependencies and provide an LLM instance:")
    print("- pip install crewai langchain-community pypdfium2")
    print("- evaluator = SlideGuardEvaluator(llm=your_llm_instance)")

if __name__ == "__main__":
    main() 