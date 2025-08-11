"""
Configuration module for SlideGuard
"""

import os
from typing import Optional, Dict, Any
from pathlib import Path

class SlideGuardConfig:
    """Configuration class for SlideGuard"""
    
    def __init__(self):
        self.api_key = os.getenv('SLIDEGUARD_LLM_API_KEY')
        self.api_base = os.getenv('SLIDEGUARD_LLM_API_BASE')
        self.model = os.getenv('SLIDEGUARD_LLM_MODEL', '/model')
        self.cache_dir = os.getenv('SLIDEGUARD_CACHE_DIR', '.slideguard_cache')
        self.file_cache_dir = os.getenv('SLIDEGUARD_FILE_CACHE_DIR', '.file_cache')
    
    def is_configured(self) -> bool:
        """Check if required environment variables are set"""
        return bool(self.api_key and self.api_base)
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration dictionary"""
        return {
            'api_key': self.api_key,
            'api_base': self.api_base,
            'model': self.model
        }
    
    def print_config_status(self):
        """Print current configuration status"""
        print("SlideGuard Configuration Status:")
        print(f"  API Key: {'✓ Set' if self.api_key else '✗ Not set'}")
        print(f"  API Base: {'✓ Set' if self.api_base else '✗ Not set'}")
        print(f"  Model: {self.model}")
        print(f"  Cache Dir: {self.cache_dir}")
        print(f"  File Cache Dir: {self.file_cache_dir}")
        
        # Check .env file status
        env_file = Path('.env')
        if env_file.exists():
            print(f"  .env file: ✓ Found at {env_file}")
        else:
            print("  .env file: ✗ Not found")
        
        if self.is_configured():
            print("  Status: ✓ Ready for evaluation")
        else:
            print("  Status: ✗ Not configured")
            print("\nTo configure, you can:")
            print("  1. Create a .env file:")
            print("     python -m slideguard.config create_env_file")
            print("  2. Set environment variables:")
            print("     export SLIDEGUARD_LLM_API_KEY='your-api-key'")
            print("     export SLIDEGUARD_LLM_API_BASE='http://localhost:8000/v1'")
            print("     export SLIDEGUARD_LLM_MODEL='/model'  # Optional, defaults to '/model'")

def create_env_file():
    """Create a .env file template"""
    env_content = """# SlideGuard Environment Configuration

# LLM Configuration
SLIDEGUARD_LLM_API_KEY=your-api-key-here
SLIDEGUARD_LLM_API_BASE=http://localhost:8000/v1
SLIDEGUARD_LLM_MODEL=/model

# Cache Configuration (optional)
SLIDEGUARD_CACHE_DIR=.slideguard_cache
SLIDEGUARD_FILE_CACHE_DIR=.file_cache

# Examples for different services:
# 
# For vLLM server:
# SLIDEGUARD_LLM_API_KEY=sk-1234567890abcdef
# SLIDEGUARD_LLM_API_BASE=http://localhost:8000/v1
# 
# For OpenAI:
# SLIDEGUARD_LLM_API_KEY=sk-your-openai-key
# SLIDEGUARD_LLM_API_BASE=https://api.openai.com/v1
# 
# For other OpenAI-compatible services:
# SLIDEGUARD_LLM_API_KEY=your-api-key
# SLIDEGUARD_LLM_API_BASE=https://your-service.com/v1
"""
    
    env_file = Path('.env')
    if env_file.exists():
        print(f"Warning: {env_file} already exists")
        return
    
    with open(env_file, 'w') as f:
        f.write(env_content)
    
    print(f"Created {env_file} template")
    print("Edit this file with your actual configuration values")

def load_dotenv_if_available():
    """Load .env file if python-dotenv is available"""
    try:
        from dotenv import load_dotenv
        env_file = Path('.env')
        if env_file.exists():
            load_dotenv()
            print(f"✓ Loaded environment variables from {env_file}")
            return True
        else:
            # .env file doesn't exist, but that's okay
            return False
    except ImportError:
        env_file = Path('.env')
        if env_file.exists():
            print(f"Warning: Found {env_file} but python-dotenv is not installed")
            print("Install with: pip install python-dotenv")
        return False

# Auto-load .env file if available FIRST
load_dotenv_if_available()

# Then create global config instance
config = SlideGuardConfig()

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "create_env_file":
        create_env_file()
    else:
        config.print_config_status() 