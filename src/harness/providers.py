"""Swappable model-provider interface and OpenAI implementation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from harness.tools import Tool


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    arguments: dict[str, Any]
    output: Any


@dataclass(frozen=True)
class ModelResult:
    output: str
    tool_calls: tuple[ToolCallRecord, ...]


class LLMProvider(Protocol):
    """Provider boundary used by the harness."""

    def run(
        self,
        *,
        user_input: str,
        instructions: str,
        tools: Sequence[Tool],
        require_tool: bool = False,
    ) -> ModelResult:
        """Generate a final response after executing requested tools."""


class OpenAIProvider:
    """OpenAI Responses API provider with an explicit tool-execution loop."""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        *,
        client: Any | None = None,
        max_tool_rounds: int = 3,
    ) -> None:
        if max_tool_rounds < 1:
            raise ValueError("max_tool_rounds must be at least 1")
        self.model = model
        self._client = client
        self.max_tool_rounds = max_tool_rounds

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The OpenAI SDK is required; install the project with `pip install -e .`."
                ) from exc
            self._client = OpenAI()
        return self._client

    def run(
        self,
        *,
        user_input: str,
        instructions: str,
        tools: Sequence[Tool],
        require_tool: bool = False,
    ) -> ModelResult:
        tool_map = {tool.name: tool for tool in tools}
        if len(tool_map) != len(tools):
            raise ValueError("Tool names must be unique")

        input_items: list[Any] = [{"role": "user", "content": user_input}]
        records: list[ToolCallRecord] = []
        response = self._create_response(
            input_items,
            instructions,
            tools,
            tool_choice="required" if require_tool else "auto",
        )

        for round_number in range(self.max_tool_rounds + 1):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                output = response.output_text.strip()
                if not output:
                    raise RuntimeError("Model returned no final text")
                return ModelResult(output=output, tool_calls=tuple(records))

            if round_number >= self.max_tool_rounds:
                raise RuntimeError("Model exceeded the configured tool-call limit")

            input_items.extend(response.output)
            for call in calls:
                tool = tool_map.get(call.name)
                if tool is None:
                    raise RuntimeError(f"Model requested unknown tool: {call.name}")
                arguments = json.loads(call.arguments)
                if not isinstance(arguments, dict):
                    raise RuntimeError("Tool arguments must decode to a JSON object")
                result = tool.invoke(arguments)
                records.append(
                    ToolCallRecord(name=call.name, arguments=arguments, output=result)
                )
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result),
                    }
                )

            next_choice = (
                "none" if round_number + 1 >= self.max_tool_rounds else "auto"
            )
            response = self._create_response(
                input_items, instructions, tools, tool_choice=next_choice
            )

        raise RuntimeError("Model did not produce a final response")

    def _create_response(
        self,
        input_items: list[Any],
        instructions: str,
        tools: Sequence[Tool],
        *,
        tool_choice: str,
    ) -> Any:
        return self.client.responses.create(
            model=self.model,
            instructions=instructions,
            input=input_items,
            tools=[tool.as_openai_tool() for tool in tools],
            tool_choice=tool_choice,
            parallel_tool_calls=False,
            store=False,
        )
