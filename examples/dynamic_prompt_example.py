"""
Example: Dynamic Prompt Generation with Slide Type Extensions

This example demonstrates how the slide_helper_type prompt is dynamically
generated from the slide type manager, and how adding new slide types
automatically updates the prompt.
"""

from slideguard.criteria.slide_types import (
    add_slide_type, 
    slide_type_manager,
    get_slide_type_prompt_section
)
from slideguard.criteria.slide_helper_type import get_slide_helper_type_prompt

def demonstrate_dynamic_prompt():
    """Demonstrate how the prompt changes when slide types are added"""
    print("=== Dynamic Prompt Generation Demo ===")
    
    # Show initial prompt
    print("1. Initial prompt with default slide types:")
    print("-" * 50)
    initial_prompt = get_slide_helper_type_prompt()
    print(initial_prompt)
    print("\n" + "=" * 80 + "\n")
    
    # Add a new slide type
    print("2. Adding new slide type 'Methodology'...")
    add_slide_type(
        name="Methodology",
        description="slide that describes the research methodology, approach, or methods used in the study or project.",
        category="content"
    )
    
    # Show updated prompt
    print("3. Updated prompt with new slide type:")
    print("-" * 50)
    updated_prompt = get_slide_helper_type_prompt()
    print(updated_prompt)
    print("\n" + "=" * 80 + "\n")
    
    # Add another slide type
    print("4. Adding another slide type 'Q&A'...")
    add_slide_type(
        name="Q&A",
        description="slide for question and answer session, usually at the end of the presentation.",
        category="interactive"
    )
    
    # Show final prompt
    print("5. Final prompt with both new slide types:")
    print("-" * 50)
    final_prompt = get_slide_helper_type_prompt()
    print(final_prompt)

def demonstrate_prompt_sections():
    """Demonstrate different ways to access prompt sections"""
    print("\n=== Prompt Section Access ===")
    
    # Get just the slide type descriptions section
    print("Slide type descriptions section:")
    print("-" * 30)
    section = get_slide_type_prompt_section()
    print(section)
    
    # Get prompt with custom template variables
    print("\nPrompt with custom template variables:")
    print("-" * 40)
    custom_prompt = get_slide_helper_type_prompt(
        schema_format="CUSTOM_SCHEMA_FORMAT",
        description="CUSTOM_DESCRIPTION_PLACEHOLDER"
    )
    print(custom_prompt)

def demonstrate_slide_type_info():
    """Show how slide type information is used in prompts"""
    print("\n=== Slide Type Information ===")
    
    # Get info about a specific slide type
    goal_info = slide_type_manager.get_slide_type_info("Goal")
    if goal_info:
        print(f"Goal slide type info:")
        print(f"  Name: {goal_info.name}")
        print(f"  Description: {goal_info.description}")
        print(f"  Category: {goal_info.category}")
    
    # Show how this description appears in the prompt
    print(f"\nThis description appears in the prompt as:")
    print(f"5) Goal - {goal_info.description}")

def demonstrate_extended_workflow():
    """Demonstrate complete workflow with extended slide types"""
    print("\n=== Complete Extended Workflow ===")
    
    # Add multiple new slide types for a specific domain
    print("Adding domain-specific slide types...")
    
    add_slide_type(
        name="Literature Review",
        description="slide that summarizes relevant literature, research background, and related work in the field.",
        category="academic",
        aliases=["Lit Review", "Background", "Related Work"],
        metadata={"requires_citations": True, "typical_position": "early"}
    )
    
    add_slide_type(
        name="Future Work",
        description="slide that outlines future research directions, potential improvements, and next steps for the project.",
        category="content",
        metadata={"typical_position": "late", "optional": True}
    )
    
    add_slide_type(
        name="References",
        description="slide containing bibliography, citations, and references used in the presentation.",
        category="academic",
        metadata={"requires_citations": True, "typical_position": "end"}
    )
    
    # Show the complete prompt with all slide types
    print("\nComplete prompt with all slide types (including new ones):")
    print("-" * 60)
    complete_prompt = get_slide_helper_type_prompt()
    print(complete_prompt)
    
    # Show slide types by category
    print(f"\nSlide types by category:")
    for category in slide_type_manager.get_categories():
        types = slide_type_manager.get_slide_types_by_category(category)
        print(f"  {category}: {types}")

if __name__ == "__main__":
    print("SlideGuard Dynamic Prompt Generation Examples")
    print("=" * 60)
    
    demonstrate_dynamic_prompt()
    demonstrate_prompt_sections()
    demonstrate_slide_type_info()
    demonstrate_extended_workflow()
    
    print("\n" + "=" * 60)
    print("Dynamic prompt generation demo completed!")
    print("\nKey benefits:")
    print("1. Slide types and their descriptions are centrally managed")
    print("2. Adding new slide types automatically updates the prompt")
    print("3. The prompt is always consistent with the slide type definitions")
    print("4. Template variables allow customization of schema format and description")
    print("5. Rich metadata and aliases support advanced use cases")
