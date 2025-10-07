"""
LangChain-oriented LLM wrapper with error-aware structured output retries and image support
"""

import base64
import json
import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel

from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompt_values import ChatPromptValue, PromptValue
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langchain.output_parsers import RetryWithErrorOutputParser
from langchain_openai.chat_models.base import ChatOpenAI

from slideguard.utils.config import SlideGuardConfig, load_config

logger = logging.getLogger(__name__)


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
        s = re.sub(r"\\+\(", "(", s)
        s = re.sub(r"\\+\)", ")", s)
        s = re.sub(r"\\+\[", "[", s)
        s = re.sub(r"\\+\]", "]", s)
        s = re.sub(r"\\(?![\"\\/bfnrtu])", "", s)
        return s
    except Exception as e:
        logger.warning(f"Failed to clean output: {s} - {e}", exc_info=True)
        return s


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
        return "Заполняй значения в JSON схеме ТОЛЬКО на русском языке."
    else:
        return "Fill values of JSON schema ONLY in English."

class ControlledLLM:
    def __init__(
        self,
        chat_model: Runnable[[PromptValue], ControlledOutput],
        max_retries: int = 3,
        retry_temperature: float = 0.01,
        preprocessors: Optional[List[Callable[[str], str]]] = None,
    ) -> None:
        self.chat_model = chat_model
        self.max_retries = max_retries
        self.retry_temperature = retry_temperature
        self.preprocessors = preprocessors or [default_text_cleaner]

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
        )

    def with_structured_output_retry(self, output_model: Type[BaseModel]) -> Runnable:
        """Runs prompt through the LLM and tries to parse the output using the output model.

        Appends parser.get_format_instructions() to the prompt
        """
        parser = PydanticOutputParser(pydantic_object=output_model)
        retry_llm = self.chat_model.bind(temperature=self.retry_temperature)
        retry_parser = RetryWithErrorOutputParser.from_llm(parser=parser, llm=retry_llm)

        async def _run(pv: PromptValue, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
            prompt_value = _ensure_image_messages(pv)
            try:
                fmt = parser.get_format_instructions()
                lang_instructions = get_language_instructions(AppLanguage.EN)
                if isinstance(prompt_value, ChatPromptValue):
                    extended_messages = list(prompt_value.messages) + [HumanMessage(content=f"{fmt}\n\n{lang_instructions}")]
                    prompt_value = ChatPromptValue(messages=extended_messages)
            except Exception as e:
                logger.error(f"Failed to extend messages: {e}", exc_info=True)
                pass

            msg: BaseMessage = await self.chat_model.ainvoke(prompt_value, config)
            text = getattr(msg, "content", str(msg))

            parsed_obj: Optional[BaseModel] = None
            raw_out: str = text
            current_text: str = text
            
            # custom parse-retry loop
            total_attempts = max(1, self.max_retries)
            for attempt_no in range(1, total_attempts + 1):
                cleaned = current_text
                for fn in self.preprocessors:
                    cleaned = fn(cleaned)
                try:
                    parsed_obj = await parser.aparse(cleaned)
                    raw_out = cleaned
                    break
                except Exception as e:
                    logger.info(f"({attempt_no}/{total_attempts}) Failed to parse output: {e}")
                    if attempt_no == total_attempts:
                        break
                    try:
                        parsed_obj = await retry_parser.aparse_with_prompt(cleaned, prompt_value)
                        raw_out = json.dumps(parsed_obj.model_dump())
                        break
                    except Exception as e:
                        logger.info(f"({attempt_no}/{total_attempts}) Failed to parse output with retry: {e}")
                        current_text = cleaned
                        continue

            if parsed_obj is None:
                try:
                    data = json.loads(default_text_cleaner(current_text))
                    parsed_obj = output_model.model_validate(data)
                    raw_out = current_text
                except Exception as e:
                    logger.warning(f"Failed to parse output after {total_attempts} attempts: {e}. Returning only raw output.")
                    parsed_obj = None
                    raw_out = current_text

            return ControlledOutput(raw=raw_out, json=parsed_obj.model_dump() if parsed_obj else None, pydantic=parsed_obj)

        return RunnableLambda(_run)

def create_llm_from_config(config: SlideGuardConfig) -> Optional[ControlledLLM]:
    if not config.is_configured():
        try:
            config = load_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
        return None

    llm_config = config.get_llm_config()
    chat = ChatOpenAI(
        **llm_config,
        temperature=0.01,
        max_tokens=5000
    )
    return ControlledLLM(chat_model=chat, max_retries=3, retry_temperature=0.01)