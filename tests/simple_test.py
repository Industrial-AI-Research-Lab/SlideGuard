"""
Simple test to verify the basic structure of the SlideGuard crew system
"""

def test_basic_structure():
    """Test basic module structure"""
    print("Testing Basic Module Structure...")
    
    # Test that we can import basic modules
    try:
        import slideguard.criteria.base
        print("✓ Criteria base module imported")
    except ImportError as e:
        print(f"✗ Could not import criteria base: {e}")
        return False
    
    try:
        import slideguard.crew.agents
        print("✓ Crew agents module imported")
    except ImportError as e:
        print(f"✗ Could not import crew agents: {e}")
        return False
    
    try:
        import slideguard.crew.evaluator
        print("✓ Crew evaluator module imported")
    except ImportError as e:
        print(f"✗ Could not import crew evaluator: {e}")
        return False
    
    print("✓ Basic structure tests passed!")
    return True

def test_file_structure():
    """Test that all required files exist"""
    print("\nTesting File Structure...")
    
    import os
    
    required_files = [
        "slideguard/criteria/__init__.py",
        "slideguard/criteria/base.py",
        "slideguard/criteria/slide_helper_description.py",
        "slideguard/criteria/slide_visual_arrangement.py",
        "slideguard/criteria/deck_structure_analysis.py",
        "slideguard/criteria/slide_helper_type.py",
        "slideguard/criteria/slide_color_analysis.py",
        "slideguard/criteria/slide_content_quality.py",
        "slideguard/crew/agents.py",
        "slideguard/crew/evaluator.py",
        "slideguard/crew/README.md",
        "slideguard/example_usage.py"
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✓ {file_path} exists")
        else:
            print(f"✗ {file_path} missing")
            return False
    
    print("✓ File structure tests passed!")
    return True

def main():
    """Run basic tests"""
    print("SlideGuard Crew System Basic Tests")
    print("=" * 40)
    
    structure_ok = test_basic_structure()
    files_ok = test_file_structure()
    
    print("\n" + "=" * 40)
    if structure_ok and files_ok:
        print("✓ All basic tests passed!")
        print("\nThe SlideGuard crew system structure is ready.")
        print("To use the full functionality, install required dependencies:")
        print("- pip install pydantic crewai langchain-community pypdfium2")
    else:
        print("✗ Some basic tests failed.")
        print("Please check the file structure and dependencies.")

if __name__ == "__main__":
    main() 