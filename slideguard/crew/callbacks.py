import re
from typing import Any, Dict, List, Optional

from langchain_core.callbacks.base import BaseCallbackHandler
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler


_DATA_URI_PATTERN = re.compile(r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+")


def _redact(obj: Any) -> Any:
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
    except Exception:
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
        except Exception:
            pass

    def on_llm_end(self, response, **kwargs: Any) -> None:  # type: ignore[override]
        try:
            self._inner.on_llm_end(response, **_redact(kwargs))
        except Exception:
            pass

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            self._inner.on_llm_error(error, **_redact(kwargs))
        except Exception:
            pass

    # Chain events
    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> None:
        try:
            self._inner.on_chain_start(_redact(serialized), _redact(inputs), **_redact(kwargs))
        except Exception:
            pass

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        try:
            self._inner.on_chain_end(_redact(outputs), **_redact(kwargs))
        except Exception:
            pass

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            self._inner.on_chain_error(error, **_redact(kwargs))
        except Exception:
            pass

    # Tool/events etc. delegate without redaction unless dicts/strings
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        try:
            self._inner.on_tool_start(_redact(serialized), _redact(input_str), **_redact(kwargs))
        except Exception:
            pass

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        try:
            self._inner.on_tool_end(_redact(output), **_redact(kwargs))
        except Exception:
            pass

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        try:
            self._inner.on_tool_error(error, **_redact(kwargs))
        except Exception:
            pass


