import asyncio

from langchain_core.messages import HumanMessage
from langchain_core.prompt_values import ChatPromptValue
from langchain_core.runnables import RunnableLambda
from pydantic import BaseModel

from slideguard.crew.controlled_llm import ControlledLLM, extract_json_payload


class ExampleOutput(BaseModel):
    title: str
    summary: str


def test_extract_json_payload_from_fenced_block() -> None:
    payload = """
Here is the JSON:

```json
{"title":"Step 3","summary":"Wrapped in fences"}
```
"""

    assert extract_json_payload(payload) == '{"title":"Step 3","summary":"Wrapped in fences"}'


def test_extract_json_payload_from_prose_wrapped_output() -> None:
    payload = """
Model response:

The answer is below.
{
  "title": "Step 3",
  "summary": "Wrapped in prose"
}

Thanks.
"""

    assert extract_json_payload(payload) == '{\n  "title": "Step 3",\n  "summary": "Wrapped in prose"\n}'


def test_controlled_llm_parses_fenced_json_output() -> None:
    async def fake_llm(_: ChatPromptValue) -> str:
        return """
```json
{
  "title": "Step 3",
  "summary": "Wrapped in fences"
}
```
"""

    llm = ControlledLLM(chat_model=RunnableLambda(fake_llm))
    chain = llm.with_structured_output_retry(ExampleOutput)
    prompt = ChatPromptValue(messages=[HumanMessage(content="Return structured output")])

    result = asyncio.run(chain.ainvoke(prompt))

    assert result.pydantic == ExampleOutput(title="Step 3", summary="Wrapped in fences")
    assert result.json == {"title": "Step 3", "summary": "Wrapped in fences"}
