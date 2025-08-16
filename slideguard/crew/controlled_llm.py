"""
Main evaluator for slide deck analysis using CrewAI agents
"""

import base64
import logging
import re
from threading import Semaphore
from typing import List, Literal, Optional, Dict, Any, Type, Union

from slideguard.utils.config import SlideGuardConfig
from crewai.llm import LLM
from pydantic import BaseModel


logger = logging.getLogger(__name__)


def encode_image_to_base64(image_path):
    if image_path.startswith("data:") or image_path.startswith("http") or image_path.startswith("https"):
        return image_path

    """Convert local image to base64 string"""
    with open(image_path, "rb") as image_file:
        image_str = base64.b64encode(image_file.read()).decode('utf-8')
    
    return f"data:image/png;base64,{image_str}"

class ControlledLLM(LLM):
    def __init__(
        self,
        model: str,
        timeout: Optional[Union[float, int]] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        n: Optional[int] = None,
        stop: Optional[Union[str, List[str]]] = None,
        max_completion_tokens: Optional[int] = None,
        max_tokens: Optional[int] = None,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        logit_bias: Optional[Dict[int, float]] = None,
        response_format: Optional[Type[BaseModel]] = None,
        seed: Optional[int] = None,
        logprobs: Optional[int] = None,
        top_logprobs: Optional[int] = None,
        base_url: Optional[str] = None,
        api_base: Optional[str] = None,
        api_version: Optional[str] = None,
        api_key: Optional[str] = None,
        callbacks: List[Any] = [],
        reasoning_effort: Optional[Literal["none", "low", "medium", "high"]] = None,
        stream: bool = False,
        max_concurrency: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(
            model=model,
            timeout=timeout,
            temperature=temperature,
            top_p=top_p,
            n=n,
            stop=stop,
            max_completion_tokens=max_completion_tokens,
            max_tokens=max_tokens,
            presence_penalty=presence_penalty,
            frequency_penalty=frequency_penalty,
            logit_bias=logit_bias,
            response_format=response_format,
            seed=seed,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
            base_url=base_url,
            api_base=api_base,
            api_version=api_version,
            api_key=api_key,
            callbacks=callbacks,
            reasoning_effort=reasoning_effort,
            stream=stream,
            **kwargs
        )
        self.max_concurrency = max_concurrency
        self._semaphore = Semaphore(max_concurrency) if max_concurrency and max_concurrency > 0 else None

    def call(
        self,
        messages: Union[str, List[Dict[str, str]]],
        tools: Optional[List[dict]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        from_task: Optional[Any] = None,
        from_agent: Optional[Any] = None,
    ) -> Union[str, Any]:
        def process_message_with_image(message: Dict[str, str]) -> str:
            if not(message.get("role", None) == "user" and "content" in message):
                return message
            
            text = message["content"]
            
            m = re.search(r"```image\s+(.*?)\s*```", text, re.DOTALL)
            content = m.group(1).strip() if m else None

            if content is None:
                return message
            
            clean_text = re.sub(r"```image[\s\S]*?```", "", text)
            
            image_url = encode_image_to_base64(content)
            
            user_message = {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": clean_text
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    }
                ]
            }

            return user_message

        messages = [process_message_with_image(m) for m in messages]

        if self._semaphore:
            with self._semaphore:
                return super().call(
                    messages=messages,  
                    tools=tools,
                    callbacks=callbacks,
                    available_functions=available_functions,
                    from_task=from_task,
                    from_agent=from_agent
                )
        
        return super().call(
            messages=messages, 
            tools=tools, 
            callbacks=callbacks, 
            available_functions=available_functions, 
            from_task=from_task, 
            from_agent=from_agent
        )

def create_llm_from_config(config: SlideGuardConfig) -> ControlledLLM | None:
    """
    Create LLM instance from environment variables for CrewAI.
    
    Environment variables:
    - SLIDEGUARD_LLM_API_KEY: API key for the LLM service
    - SLIDEGUARD_LLM_API_BASE: Base URL for the LLM API (e.g., http://localhost:8000/v1)
    - SLIDEGUARD_LLM_MODEL: Model name (defaults to '/model')
    
    Returns:
        LLM instance compatible with CrewAI or None if environment variables are not set
    """
    if not config.is_configured():
        logger.warning("LLM environment variables not set")
        logger.warning("Set SLIDEGUARD_LLM_API_KEY and SLIDEGUARD_LLM_API_BASE to enable full evaluation")
        return None
    
    try:
        
        # Configure CrewAI to use LiteLLM with explicit provider
        # and wrap with a semaphore for bounded concurrency
        llm = ControlledLLM(
            model=f"openai/{config.model}",  # Tell LiteLLM this is an OpenAI-compatible model
            api_key=config.api_key,
            base_url=config.api_base,
            temperature=0.1,
            max_tokens=4000,
            max_concurrency=config.max_concurrency
        )
        
        return llm
        
    except ImportError:
        logger.warning("langchain-openai package not installed. Install with: pip install langchain-openai")
        return None
    except Exception as e:
        logger.error(f"Error creating LLM instance: {e}")
        return None

