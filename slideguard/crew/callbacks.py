"""
Custom callbacks for SlideGuard.
"""

import re
from typing import Any, Dict, List
from contextlib import contextmanager
from typing import Iterator, Optional
from langfuse import Langfuse
import logging

from langchain_core.callbacks.base import BaseCallbackHandler
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

logger = logging.getLogger(__name__)


_DATA_URI_PATTERN = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+")


def _redact(obj: Any) -> Any:
    """Replace base64 image data URIs with a placeholder string."""
    try:
        if obj is None:
            return obj
        if isinstance(obj, str):
            return _DATA_URI_PATTERN.sub("[REDACTED_IMAGE_DATA_URI]", obj)
        if isinstance(obj, (list, tuple)):
            return obj.__class__(_redact(x) for x in obj)
        if isinstance(obj, dict):
            return {k: _redact(v) for k, v in obj.items()}
        return obj
    except Exception as e:
        logger.warning(f"Failed to redact object: {obj} - {e}", exc_info=True)
        return obj


class ImageStrippingLangfuseHandler(BaseCallbackHandler):
    """LangChain callback that redacts base64 image data URIs before delegating to Langfuse.

    This prevents Langfuse from detecting and uploading media while preserving traces.
    """

    def __init__(self) -> None:
        self._inner = LangfuseCallbackHandler()

    # LLM events
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        try:
            self._inner.on_llm_start(_redact(serialized), _redact(prompts), **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_llm_start: {e}", exc_info=True)
            pass

    def on_llm_end(self, response, **kwargs: Any) -> None:  # type: ignore[override]
        try:
            self._inner.on_llm_end(response, **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_llm_end: {e}", exc_info=True)
            pass

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            self._inner.on_llm_error(error, **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_llm_error: {e}", exc_info=True)
            pass

    # Chain events
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        try:
            self._inner.on_chain_start(_redact(serialized), _redact(inputs), **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_chain_start: {e}", exc_info=True)
            pass

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        try:
            self._inner.on_chain_end(_redact(outputs), **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_chain_end: {e}", exc_info=True)
            pass

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            self._inner.on_chain_error(error, **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_chain_error: {e}", exc_info=True)
            pass

    # Tool/events etc. delegate without redaction unless dicts/strings
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        try:
            self._inner.on_tool_start(_redact(serialized), _redact(input_str), **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_tool_start: {e}", exc_info=True)
            pass

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        try:
            self._inner.on_tool_end(_redact(output), **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_tool_end: {e}", exc_info=True)
            pass

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            self._inner.on_tool_error(error, **_redact(kwargs))
        except Exception as e:
            logger.warning(f"Exception in on_tool_error: {e}", exc_info=True)
            pass



@contextmanager
def langfuse_callback_cm(langfuse_client: Optional[Langfuse]) -> Iterator[List[Any]]:
    callbacks: List[Any] = []
    try:
        if langfuse_client:
            callbacks = [ImageStrippingLangfuseHandler()]
        yield callbacks
    finally:
        if langfuse_client:
            try:
                langfuse_client.flush()
            except Exception as e:
                logger.warning(f"Failed to flush langfuse client: {e}", exc_info=True)
                pass
