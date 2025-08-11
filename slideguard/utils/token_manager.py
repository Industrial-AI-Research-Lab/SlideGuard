"""
Token management for API rate limiting and concurrency control.

This module provides functionality for managing API tokens and controlling
concurrent access to API resources. It includes semaphore management and
token rotation capabilities.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

class TokenManager:
    """Manager for API tokens with rate limiting and rotation.
    
    This class manages a pool of API tokens, handling rate limiting and token
    rotation to ensure optimal API usage and prevent rate limit errors.
    """

    def __init__(self, cache_dir: str = ".token_cache"):
        """Initialize the token manager.
        
        Args:
            cache_dir: Directory to store token cache
        """
        self.cache_dir = cache_dir
        self._ensure_cache_dir()

    def _ensure_cache_dir(self):
        """Ensure cache directory exists."""
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_token_cache_path(self) -> str:
        """Get path to token cache file."""
        return os.path.join(self.cache_dir, 'token_cache.json')

    def _load_cached_token(self) -> Optional[Tuple[str, int]]:
        """Load token and expiry from cache if exists and not expired."""
        cache_path = self._get_token_cache_path()
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                if cache['expires_at'] > time.time() * 1000:  # Convert to milliseconds
                    return cache['access_token'], cache['expires_at']
        return None

    def _save_token_cache(self, token: str, expires_at: int) -> None:
        """Save token and expiry to cache."""
        cache_path = self._get_token_cache_path()
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump({
                'access_token': token,
                'expires_at': expires_at
            }, f)

    def get_access_token(self) -> str:
        """Get a valid access token, either from cache or by requesting a new one."""
        cached = self._load_cached_token()
        if cached:
            return cached[0]

        # TODO: Implement actual token refresh logic here
        # For now, just return a dummy token
        token = "dummy_token"
        expires_at = int(time.time() * 1000) + 3600000  # 1 hour from now
        self._save_token_cache(token, expires_at)
        return token

    def get_token_balance(self) -> dict:
        """Get the current token balance from Qwen API."""
        # Note: Token balance checking not supported for local vLLM servers
        return {"message": "Token balance checking not supported for local vLLM servers"}

    @staticmethod
    def log_token_usage(response):
        """Log token usage from response metadata if available"""
        if hasattr(response, 'response_metadata') and response.response_metadata:
            logger.info(f"Token usage metadata: {response.response_metadata}")
        else:
            logger.info("No token usage metadata available in response")

    @staticmethod
    def estimate_tokens(model, text):
        """Estimate token count for a message using Qwen's method"""
        try:
            token_count = model.get_num_tokens_from_messages([(None, text)])
            logger.info(f"Estimated token count for message: {token_count}")
            return token_count
        except Exception as e:
            logger.error(f"Error estimating tokens: {e}")
            return None

    @staticmethod
    def estimate_remaining_requests(token_usage: Dict[str, Any], balance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate remaining requests based on current usage and balance."""
        estimates = {}
        
        # Create balance lookup by model
        balance_by_model = {item['usage']: item['value'] for item in balance_data['balance']}
        
        for model, usage in token_usage.items():
            if model not in balance_by_model:
                logger.warning(f"No balance data for model: {model}")
                continue
                
            remaining_balance = balance_by_model[model]
            avg_tokens_per_request = usage.total_tokens / usage.request_count if usage.request_count > 0 else 0
            
            if avg_tokens_per_request > 0:
                estimated_requests = remaining_balance / avg_tokens_per_request
                estimates[model] = {
                    'avg_tokens_per_request': avg_tokens_per_request,
                    'remaining_balance': remaining_balance,
                    'estimated_remaining_requests': int(estimated_requests),
                    'tokens_used': usage.total_tokens,
                    'token_usage_percent': (usage.total_tokens / (usage.total_tokens + remaining_balance)) * 100
                }
                
        return estimates
