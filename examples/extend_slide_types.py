"""
Example: How to Extend Slide Types in SlideGuard

This example demonstrates the convenient ways to add new slide types
to the SlideGuard system.
"""

from slideguard.criteria.slide_types import (
    slide_type_manager, 
    add_slide_type, 
    get_slide_types, 
    get_slide_types_by_category,
    validate_slide_type
)

def example_basic_extension():
    """Example 1: Basic slide type extension"""
    print("=== Basic Slide Type Extension ===")
    
    # Add a new slide type
    success = add_slide_type(
        name="Methodology",
        description="Slide describing the research methodology or approach used",
        category="content"
    )
    
    if success:
        print("✓ Added 'Methodology' slide type")
    else:
        print("✗ 'Methodology' slide type already exists")
    
    # Check all slide types
    all_types = get_slide_types()
    print(f"All slide types: {all_types}")

def example_advanced_extension():
    """Example 2: Advanced slide type extension with aliases and metadata"""
    print("\n=== Advanced Slide Type Extension ===")
    
    # Add a slide type with aliases and metadata
    success = slide_type_manager.add_slide_type(
        name="Literature Review",
        description="Slide summarizing relevant literature and research background",
        category="content",
        aliases=["Lit Review", "Background", "Related Work"],
        metadata={
            "requires_citations": True,
            "typical_position": "early",
            "complexity": "medium"
        }
    )
    
    if success:
        print("✓ Added 'Literature Review' slide type with aliases and metadata")
        
        # Show the slide type info
        info = slide_type_manager.get_slide_type_info("Literature Review")
        print(f"  Description: {info.description}")
        print(f"  Category: {info.category}")
        print(f"  Aliases: {info.aliases}")
        print(f"  Metadata: {info.metadata}")
    else:
        print("✗ 'Literature Review' slide type already exists")

def example_category_management():
    """Example 3: Working with slide type categories"""
    print("\n=== Category Management ===")
    
    # Add slide types to different categories
    add_slide_type("Q&A", "Question and answer slide", category="interactive")
    add_slide_type("References", "Bibliography and references slide", category="academic")
    add_slide_type("Future Work", "Future research directions slide", category="content")
    
    # Get slide types by category
    content_types = get_slide_types_by_category("content")
    print(f"Content slide types: {content_types}")
    
    # Get all categories
    categories = slide_type_manager.get_categories()
    print(f"All categories: {categories}")

def example_validation_and_queries():
    """Example 4: Validation and querying"""
    print("\n=== Validation and Querying ===")
    
    # Validate slide types
    print(f"Is 'Goal' valid? {validate_slide_type('Goal')}")
    print(f"Is 'Invalid Type' valid? {validate_slide_type('Invalid Type')}")
    
    # Find slide type by alias
    alias_result = slide_type_manager.find_slide_type_by_alias("Lit Review")
    print(f"Found slide type for alias 'Lit Review': {alias_result}")
    
    # Get slide types with aliases
    types_with_aliases = slide_type_manager.get_slide_types_with_aliases()
    print(f"Slide types with aliases: {types_with_aliases}")

def example_import_export():
    """Example 5: Import/Export functionality"""
    print("\n=== Import/Export Functionality ===")
    
    # Export current slide types to JSON
    json_data = slide_type_manager.export_to_json()
    print("Current slide types exported to JSON:")
    print(json_data[:200] + "..." if len(json_data) > 200 else json_data)
    
    # Example of importing from JSON
    custom_types_json = '''
    {
        "Appendix": {
            "description": "Additional supporting material",
            "category": "supplementary",
            "aliases": ["Supporting Material", "Extra Info"],
            "metadata": {"optional": true}
        }
    }
    '''
    
    imported_count = slide_type_manager.import_from_json(custom_types_json)
    print(f"Imported {imported_count} new slide type(s)")

def example_criteria_integration():
    """Example 6: Integration with criteria system"""
    print("\n=== Criteria Integration ===")
    
    from slideguard.criteria import get_criteria_for_slide_types
    
    # Add a new slide type
    add_slide_type("Demo", "Live demonstration slide", category="interactive")
    
    # Use it with criteria filtering
    demo_criteria = get_criteria_for_slide_types(["Demo"])
    print(f"Criteria applicable to Demo slides: {[c.criterion_name for c in demo_criteria]}")

if __name__ == "__main__":
    print("SlideGuard Slide Type Extension Examples")
    print("=" * 50)
    
    example_basic_extension()
    example_advanced_extension()
    example_category_management()
    example_validation_and_queries()
    example_import_export()
    example_criteria_integration()
    
    print("\n" + "=" * 50)
    print("Extension examples completed!")
    print("\nTo use these new slide types in your criteria:")
    print("1. Add them using add_slide_type()")
    print("2. Reference them in your criterion's applicable_slide_types")
    print("3. They'll automatically be available in the criteria system")
