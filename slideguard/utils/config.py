"""
Configuration module for SlideGuard
"""

import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path


from dotenv import load_dotenv
from langfuse import Langfuse, get_client


logger = logging.getLogger(__name__)


class SlideGuardConfig:
    """Configuration class for SlideGuard"""
    
    def __init__(self, max_concurrency: Optional[int] = None):
        self.api_key = os.getenv('SLIDEGUARD_LLM_API_KEY')
        self.api_base = os.getenv('SLIDEGUARD_LLM_API_BASE')
        self.model = os.getenv('SLIDEGUARD_LLM_MODEL', '/model')
        self.cache_dir = os.getenv('SLIDEGUARD_CACHE_DIR', '.slideguard_cache')
        self.evaluations_cache_dir = os.getenv('SLIDEGUARD_EVALUATIONS_DIR', os.path.join(self.cache_dir, 'evaluations'))
        self.file_cache_dir = os.getenv('SLIDEGUARD_FILE_CACHE_DIR', os.path.join(self.cache_dir, 'file_cache'))
        env_mc = os.getenv('SLIDEGUARD_MAX_CONCURRENCY')
        parsed_mc = int(env_mc) if env_mc and env_mc.isdigit() and int(env_mc) > 0 else None
        self.max_concurrency = max_concurrency if max_concurrency is not None else parsed_mc
    
    def is_configured(self) -> bool:
        """Check if required environment variables are set"""
        has_cloud_provider = bool(
            os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY')
        )
        return has_cloud_provider or bool(self.api_key and self.api_base)
    
    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration dictionary"""
        return {
            'api_key': self.api_key,
            'base_url': self.api_base, # in langchain-openai api_base is moved to model_kwargs, use base_url instead
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
SLIDEGUARD_EVALUATIONS_DIR=.slideguard_cache/evaluations
SLIDEGUARD_FILE_CACHE_DIR=.file_cache

# Model Configuration (optional)
SLIDEGUARD_MAX_CONCURRENCY=8

# Legacy compatibility flag (optional)
# Set to 1, true, yes, or on to force legacy chat completions API parameters
# SLIDEGUARD_FORCE_LEGACY_CHAT_COMPLETIONS=false

# Anthropic Configuration (optional, takes priority over OpenAI and local model)
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-3-5-sonnet-latest

# OpenAI Configuration (optional, takes priority over local model)
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4o

# DB config
AUTH_DB_URL=sqlite:///./auth.db

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


def load_config(max_concurrency: Optional[int] = None) -> SlideGuardConfig:
    """Load environment variables from .env file if it exists."""
    load_dotenv(override=True)
    
    return SlideGuardConfig(max_concurrency=max_concurrency)


def load_langfuse_client(use_langfuse: bool) -> Langfuse | None:
    if not use_langfuse:
        return None

    langfuse_client: Langfuse = get_client()

    if langfuse_client.auth_check():
        logger.info("Langfuse client is authenticated and ready!")
    else:
        logger.error("Langfuse Authentication failed. Please check your credentials and host.")

    return langfuse_client
