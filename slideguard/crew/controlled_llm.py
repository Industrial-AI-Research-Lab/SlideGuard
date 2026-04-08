"""
LangChain-oriented LLM wrapper with error-aware structured output retries and image support
"""

import base64
import os
import json
import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional, Type
from urllib.parse import urlparse

from pydantic import BaseModel

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.language_models import LanguageModelInput
from langchain_core.prompt_values import ChatPromptValue, PromptValue
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain.output_parsers import RetryWithErrorOutputParser
from langchain_openai.chat_models.base import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from slideguard.utils.config import SlideGuardConfig, load_config

logger = logging.getLogger(__name__)

LEGACY_CHAT_ENV_FLAG = "SLIDEGUARD_FORCE_LEGACY_CHAT_COMPLETIONS"


def _flag_enabled(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _should_use_legacy_chat_params(base_url: Optional[str]) -> bool:
    """Detect when we should keep using `max_tokens` for chat/completions APIs."""
    if _flag_enabled(os.getenv(LEGACY_CHAT_ENV_FLAG)):
        return True
    if not base_url:
        return False
    try:
        host = urlparse(base_url).netloc or base_url
    except ValueError:
        host = base_url
    host = host.lower()
    return "openai" not in host


class LegacyCompatibleChatOpenAI(ChatOpenAI):
    """ChatOpenAI flavor that keeps legacy `max_tokens` for compat servers."""

    @property
    def _default_params(self) -> dict[str, Any]:
        params = dict(super()._default_params)
        if "max_completion_tokens" in params:
            params["max_tokens"] = params.pop("max_completion_tokens")
        return params

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        # Only legacy chat/completions endpoints expect this parameter.
        if "messages" in payload and "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        return payload


def encode_image_to_base64(image_path: str) -> str:
    if image_path.startswith("data:") or image_path.startswith("http") or image_path.startswith("https"):
        return image_path
    with open(image_path, "rb") as image_file:
        image_str = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:image/png;base64,{image_str}"


def _ensure_image_messages(pv: PromptValue) -> PromptValue:
    if not isinstance(pv, ChatPromptValue):
        return pv
    msgs: List[BaseMessage] = []
    for m in pv.messages:
        if isinstance(m, HumanMessage) and isinstance(m.content, str):
            text = m.content
            match = re.search(r"```image\s+(.*?)\s*```", text, re.DOTALL)
            if match:
                path = match.group(1).strip()
                clean_text = re.sub(r"```image[\s\S]*?```", "", text)
                image_url = encode_image_to_base64(path)
                msgs.append(
                    HumanMessage(
                        content=[
                            {"type": "text", "text": clean_text},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ]
                    )
                )
                continue
        msgs.append(m)
    return ChatPromptValue(messages=msgs)


def default_text_cleaner(s: str) -> str:
    try:
        s = s.replace("\x00", "").replace("\r", "\n")
        s = s.replace("\u201c", '"').replace("\u201d", '"')
        s = s.replace("\u2018", "'").replace("\u2019", "'")
        cleaned_chars: list[str] = []
        idx = 0
        while idx < len(s):
            char = s[idx]
            if char != "\\":
                cleaned_chars.append(char)
                idx += 1
                continue

            slash_end = idx
            while slash_end < len(s) and s[slash_end] == "\\":
                slash_end += 1

            if slash_end < len(s) and s[slash_end] in "()[]":
                cleaned_chars.append(s[slash_end])
                idx = slash_end + 1
                continue

            next_char = s[idx + 1] if idx + 1 < len(s) else ""
            if next_char in '"\\/bfnrtu':
                cleaned_chars.append("\\")
            idx += 1

        return "".join(cleaned_chars)
    except Exception as e:
        logger.warning(f"Failed to clean output: {s} - {e}", exc_info=True)
        return s


def extract_json_payload(s: str) -> str:
    """Extract the first complete JSON object/array from LLM text output."""
    stripped = s.strip()
    if not stripped:
        return stripped

    decoder = json.JSONDecoder()
    for idx, char in enumerate(stripped):
        if char not in "[{":
            continue
        try:
            _, end = decoder.raw_decode(stripped[idx:])
            return stripped[idx : idx + end]
        except json.JSONDecodeError:
            continue

    return stripped


@dataclass
class ControlledOutput:
    raw: str
    json: Optional[dict]
    pydantic: Optional[BaseModel]


class AppLanguage(str, Enum):
    RU = "ru"
    EN = "en"


def get_language_instructions(language: AppLanguage) -> str: # can be set based on the presentation language
    if language == AppLanguage.RU:
        return (
            "Заполняй значения в JSON-схеме ТОЛЬКО на русском языке. "
            "Все текстовые поля (включая комментарии, рекомендации, краткие выводы и иные пояснения) "
            "должны быть написаны на грамотном русском языке. "
            "Если требуются списки или пояснения, используй русский язык для каждого пункта."
        )
    else:
        return (
            "Fill values of the JSON schema ONLY in English. "
            "All textual fields (comments, recommendations, summaries, explanations) "
            "must be written in clear English."
        )

class ControlledLLM:
    def __init__(
        self,
        chat_model: Runnable[[PromptValue], ControlledOutput],
        max_retries: int = 3,
        retry_temperature: float = 0.01,
        preprocessors: Optional[List[Callable[[str], str]]] = None,
        language: AppLanguage = AppLanguage.EN,
    ) -> None:
        self.chat_model = chat_model
        self.max_retries = max_retries
        self.retry_temperature = retry_temperature
        self.preprocessors = preprocessors or [default_text_cleaner, extract_json_payload]
        self.language: AppLanguage = language

    def with_tools(self, tools: List[Any]) -> "ControlledLLM":
        """Binds tools to the LLM"""
        if not tools:
            return self
        if hasattr(self.chat_model, "bind_tools"):
            bound = self.chat_model.bind_tools(tools)
        else:
            bound = self.chat_model.bind(tools=tools)
        return ControlledLLM(
            chat_model=bound,
            max_retries=self.max_retries,
            retry_temperature=self.retry_temperature,
            preprocessors=self.preprocessors,
            language=self.language,
        )

    def with_structured_output_retry(self, output_model: Type[BaseModel]) -> Runnable[[PromptValue], ControlledOutput]:
        """Runs prompt through the LLM and tries to parse the output using the output model.

        Appends parser.get_format_instructions() to the prompt
        """
        parser = PydanticOutputParser(pydantic_object=output_model)
        retry_llm = self.chat_model.bind(temperature=self.retry_temperature)
        retry_parser = RetryWithErrorOutputParser.from_llm(parser=parser, llm=retry_llm)

        async def _run(pv: PromptValue, config: Optional[RunnableConfig] = None) -> ControlledOutput:
            prompt_value = _ensure_image_messages(pv)
            try:
                fmt = parser.get_format_instructions()
                lang_instructions = get_language_instructions(self.language)
                if isinstance(prompt_value, ChatPromptValue):
                    extended_messages = [*prompt_value.messages, HumanMessage(content=f"{fmt}\n\n{lang_instructions}")]
                    prompt_value = ChatPromptValue(messages=extended_messages)
            except Exception as e:
                logger.error(f"Failed to extend messages: {e}", exc_info=True)
                pass

            text: str = await (self.chat_model | StrOutputParser()).ainvoke(prompt_value, config)

            parsed_obj: Optional[BaseModel] = None
            raw_out: str = text
            current_text: str = text
            
            # parse with retry logic
            attempt = 0
            max_attempts = max(1, self.max_retries + 1) # +1 for the initial parse
            
            while attempt < max_attempts and not parsed_obj:
                for fn in self.preprocessors:
                    current_text = fn(current_text)
                
                try:
                    parsed_obj = await parser.aparse(current_text) # initial parse
                    raw_out = current_text
                except Exception as e:
                    try:
                        parsed_obj = output_model.model_validate_json(current_text)
                        raw_out = current_text
                        continue
                    except Exception:
                        pass
                    if attempt < self.max_retries: # retry parse
                        logger.info(f"({attempt + 1}/{self.max_retries + 1}) Failed to parse output: {e}")
                        try:
                            parsed_obj = await retry_parser.aparse_with_prompt(current_text, prompt_value)
                            raw_out = json.dumps(parsed_obj.model_dump())
                        except Exception as retry_e:
                            logger.info(f"({attempt + 1}/{self.max_retries + 1}) Failed to parse output with retry: {retry_e}")
                    attempt += 1
            
            # Final fallback attempt
            if not parsed_obj:
                try:
                    candidate = extract_json_payload(default_text_cleaner(raw_out))
                    parsed_obj = output_model.model_validate_json(candidate)
                    raw_out = candidate
                except Exception as e:
                    logger.warning(f"Failed to parse output after {self.max_retries + 1} attempts: {e}. Returning only raw output.")
                    parsed_obj = None
                    raw_out = raw_out

            return ControlledOutput(raw=raw_out, json=parsed_obj.model_dump() if parsed_obj else None, pydantic=parsed_obj)

        return RunnableLambda(_run)

    def set_language(self, language: AppLanguage | str) -> None:
        """Set preferred language for future LLM responses."""
        try:
            if isinstance(language, str):
                language = AppLanguage(language.lower())
            self.language = language
        except Exception:
            logger.warning("Invalid language %s provided to ControlledLLM. Falling back to English.", language)
            self.language = AppLanguage.EN

class OpenAIModel(str, Enum):
    GPT_5 = "gpt-5"
    GPT_4O = "gpt-4o"


class AnthropicModel(str, Enum):
    CLAUDE_SONNET_4 = "claude-sonnet-4-20250514"
    CLAUDE_4O = "claude-4o-latest"
    CLAUDE_3_7_SONNET = "claude-3-7-sonnet-latest"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-latest"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-latest"


ANTHROPIC_MODEL_NAMES = {m.value for m in AnthropicModel}


def create_llm_from_config(config: SlideGuardConfig, language: AppLanguage = AppLanguage.EN) -> Optional[ControlledLLM]:
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not anthropic_key and not openai_key:
        if not config.is_configured():
            try:
                config = load_config()
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                return None

            if not config.is_configured():
                return None

    if anthropic_key:
        model_name = os.getenv("ANTHROPIC_MODEL", AnthropicModel.CLAUDE_3_5_SONNET.value)
        if model_name not in ANTHROPIC_MODEL_NAMES:
            logger.warning(
                f"Anthropic model '{model_name}' not in known models. "
                f"Proceeding anyway — it may be a valid model ID."
            )
        logger.info(f"Using Anthropic model: {model_name}")
        chat = ChatAnthropic(
            api_key=anthropic_key,
            model_name=model_name,
            temperature=0.01,
            max_tokens=5000,
        )
    elif openai_key:
        model_name = os.getenv("OPENAI_MODEL", OpenAIModel.GPT_4O.value)
        try:
            selected = OpenAIModel(model_name)
        except Exception:
            logger.warning(f"Failed to load OpenAI model: {model_name}. Using default model: {OpenAIModel.GPT_4O.value}")
            selected = OpenAIModel.GPT_4O
        logger.info(f"Using OpenAI model: {selected.value}")
        chat = ChatOpenAI(
            api_key=openai_key,
            model=selected.value,
            temperature=0.01,
            max_tokens=5000,
        )
    else:
        llm_config = config.get_llm_config()
        base_url = llm_config.get("base_url")
        chat_cls = (
            LegacyCompatibleChatOpenAI
            if _should_use_legacy_chat_params(base_url)
            else ChatOpenAI
        )
        if chat_cls is LegacyCompatibleChatOpenAI:
            logger.info(
                "Using legacy Chat Completions compatibility mode for base_url=%s",
                base_url,
            )
        chat = chat_cls(
            **llm_config,
            temperature=0.01,
            max_tokens=5000
        )
    return ControlledLLM(chat_model=chat, max_retries=3, retry_temperature=0.01, language=language)