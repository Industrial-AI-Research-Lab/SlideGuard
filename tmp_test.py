"""Quick test to verify the setup test works"""
import sys
sys.path.insert(0, '/Users/ngc436/Documents/projects/SlideGuard')

# Test the imports and initialization logic
try:
    from slideguard.utils.config import load_config
    from slideguard.utils.file_manager import FileManager
    from slideguard.utils.cache_manager import CacheManager
    from slideguard.crew.controlled_llm import create_llm_from_config
    from slideguard.crew.evaluator import SlideGuardEvaluator
    
    print("✓ All imports successful")
    
    config = load_config()
    print("✓ Config loaded")
    
    if config.is_configured():
        print("✓ Config is valid")
        
        llm = create_llm_from_config(config)
        if llm:
            print("✓ LLM created")
            
            evaluator = SlideGuardEvaluator(
                file_manager=FileManager(config.file_cache_dir),
                cache_manager=CacheManager(config.evaluations_cache_dir),
                llm=llm,
            )
            print("✓ Evaluator created successfully!")
            evaluator.print_status()
        else:
            print("✗ LLM creation failed")
    else:
        print("✗ Config not properly set")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
