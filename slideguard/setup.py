"""
Setup script for SlideGuard
"""

import sys
from pathlib import Path

def setup_environment():
    """Interactive setup for environment variables"""
    print("SlideGuard Setup")
    print("=" * 40)
    
    # Check if .env file exists
    env_file = Path('.env')
    if env_file.exists():
        print("Found existing .env file")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled")
            return
    
    # Get configuration from user
    print("\nPlease provide your LLM configuration:")
    
    api_key = input("API Key: ").strip()
    if not api_key:
        print("API Key is required")
        return
    
    api_base = input("API Base URL (e.g., http://localhost:8000/v1): ").strip()
    if not api_base:
        print("API Base URL is required")
        return
    
    model = input("Model name (default: /model): ").strip()
    if not model:
        model = "/model"
    
    # Create .env file
    env_content = f"""# SlideGuard Environment Configuration

# LLM Configuration
SLIDEGUARD_LLM_API_KEY={api_key}
SLIDEGUARD_LLM_API_BASE={api_base}
SLIDEGUARD_LLM_MODEL={model}

# Cache Configuration (optional)
SLIDEGUARD_CACHE_DIR=.slideguard_cache
SLIDEGUARD_EVALUATIONS_DIR=.slideguard_cache/evaluations
SLIDEGUARD_FILE_CACHE_DIR=.file_cache

# Model Configuration (optional)
SLIDEGUARD_MAX_CONCURRENCY=8

# Legacy compatibility flag (optional)
# SLIDEGUARD_FORCE_LEGACY_CHAT_COMPLETIONS=false

# OpenAI Configuration (optional)
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o

# DB config
AUTH_DB_URL=sqlite:///./auth.db
"""
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"\n✓ Created {env_file}")
    print("You can now run SlideGuard evaluations!")

def test_installation():
    """Test the installation and configuration"""
    print("Testing SlideGuard Installation")
    print("=" * 40)
    
    # Check core dependencies first
    missing_deps = []
    core_packages = [
        'pydantic',
        'dotenv',
        'langfuse',
        'langchain',
        'langchain_openai',
        'langgraph',
        'typer',
        'gradio',
        'fitz',  # PyMuPDF
        'reportlab',
    ]
    
    for package in core_packages:
        try:
            __import__(package)
        except ImportError:
            missing_deps.append(package)
    
    if missing_deps:
        print(f"✗ Missing dependencies: {', '.join(missing_deps)}")
        print("\nPlease install required dependencies:")
        print("  Using Poetry (recommended):")
        print("    poetry install")
        print("\n  Or using pip:")
        print("    pip install pydantic python-dotenv langfuse langchain langchain-openai")
        print("    pip install langgraph typer gradio PyMuPDF reportlab bcrypt")
        return
    
    try:
        # Test basic imports
        from slideguard.utils.config import load_config
        from slideguard.utils.file_manager import FileManager
        from slideguard.utils.cache_manager import CacheManager
        from slideguard.crew.controlled_llm import create_llm_from_config
        config = load_config()
        print("✓ Configuration module imported")
        
        
        from slideguard.crew.evaluator import SlideGuardEvaluator
        print("✓ Evaluator module imported")
        
        # Test configuration
        print()
        config.print_config_status()
        
        # Test evaluator initialization
        if not config.is_configured():
            print("\n✗ Configuration incomplete. Run setup first:")
            print("  python3 -m slideguard.setup setup")
            return
        
        llm = create_llm_from_config(config)
        if llm is None:
            print("\n✗ Failed to create LLM. Check your API configuration.")
            return
        
        print("✓ LLM initialized")
        
        # Test connection to vLLM server
        print("\nTesting connection to LLM server...")
        try:
            from langchain_core.messages import HumanMessage
            test_message = [HumanMessage(content="Hello, respond with 'OK'")]
            test_response = llm.chat_model.invoke(test_message)
            
            if test_response and hasattr(test_response, 'content'):
                response_text = test_response.content if hasattr(test_response, 'content') else str(test_response)
                print("✓ LLM server connection successful")
                print(f"  Model: {config.model}")
                print(f"  API Base: {config.api_base}")
                print(f"  Response preview: {response_text[:100] if response_text else '(empty)'}...")
            else:
                print("⚠ LLM server responded but returned empty response")
        except Exception as e:
            print(f"✗ LLM server connection failed: {e}")
            print("  Check that your vLLM server is running and accessible")
            print(f"  Server: {config.api_base}")
            return
        
        SlideGuardEvaluator(
            file_manager=FileManager(config.file_cache_dir),
            cache_manager=CacheManager(config.evaluations_cache_dir),
            llm=llm,
        )
        print("✓ Evaluator initialized")
        
        print("\n✓ All tests passed! SlideGuard is ready to use.")
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        print("\nPlease install required dependencies:")
        print("  Using Poetry (recommended):")
        print("    poetry install")
        print("\n  Or using pip:")
        print("    pip install pydantic python-dotenv langfuse langchain langchain-openai")
        print("    pip install langgraph typer gradio PyMuPDF reportlab bcrypt")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")

def create_example_script():
    """Create an example evaluation script"""
    example_script = """#!/usr/bin/env python3
\"\"\"
Example SlideGuard evaluation script
\"\"\"

import asyncio
from slideguard.crew.evaluator import SlideGuardEvaluator

async def main():
    # Initialize evaluator
    evaluator = SlideGuardEvaluator()
    
    # Check if LLM is available
    if evaluator.llm is None:
        print("LLM not configured. Please set environment variables.")
        return
    
    # Evaluate a presentation
    try:
        result = await evaluator.evaluate_presentation("your_presentation.pdf")
        
        print(f"Evaluation completed!")
        print(f"Overall score: {result.overall_score}")
        print(f"Summary: {result.summary}")
        
        # Print detailed results
        print("\\nDetailed Results:")
        for slide_eval in result.slide_evaluations:
            print(f"\\nSlide {slide_eval.slide_id}:")
            print(f"  Types: {slide_eval.slide_type}")
            print(f"  Evaluations: {len(slide_eval.evaluations)}")
            
            for eval_result in slide_eval.evaluations:
                print(f"    {eval_result.criterion_name}: Score {eval_result.score}")
        
    except Exception as e:
        print(f"Evaluation failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
"""
    
    script_path = Path("example_evaluation.py")
    if script_path.exists():
        print(f"Warning: {script_path} already exists")
        return
    
    with open(script_path, 'w') as f:
        f.write(example_script)
    
    # Make executable
    script_path.chmod(0o755)
    
    print(f"✓ Created {script_path}")
    print("You can run it with: python example_evaluation.py")

def main():
    """Main setup function"""
    if len(sys.argv) < 2:
        print("SlideGuard Setup")
        print("=" * 40)
        print("Usage:")
        print("  python -m slideguard.setup setup     - Configure environment")
        print("  python -m slideguard.setup test      - Test installation")
        print("  python -m slideguard.setup example   - Create example script")
        print("  python -m slideguard.setup all       - Run all setup steps")
        return
    
    command = sys.argv[1].lower()
    
    if command == "setup":
        setup_environment()
    elif command == "test":
        test_installation()
    elif command == "example":
        create_example_script()
    elif command == "all":
        setup_environment()
        print("\n" + "=" * 40)
        test_installation()
        print("\n" + "=" * 40)
        create_example_script()
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main() 