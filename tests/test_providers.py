import json
from types import SimpleNamespace

from harness.providers import OpenAIProvider
from harness.tools import Tool


class FakeResponses:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(
                type="function_call",
                name="search_kb",
                arguments='{"query":"vpn failure"}',
                call_id="call-1",
            )
            return SimpleNamespace(output=[call], output_text="")
        return SimpleNamespace(
            output=[SimpleNamespace(type="message")],
            output_text="Retry the client [vpn-access.md].",
        )


def test_openai_provider_executes_strict_tool_and_disables_storage() -> None:
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)
    tool = Tool(
        name="search_kb",
        description="Search the KB",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=lambda arguments: {
            "results": [{"source": "vpn-access.md", "query": arguments["query"]}]
        },
    )

    result = OpenAIProvider(client=client).run(
        user_input="VPN failure",
        instructions="Use the tool.",
        tools=[tool],
        require_tool=True,
    )

    assert result.output == "Retry the client [vpn-access.md]."
    assert result.tool_calls[0].name == "search_kb"
    assert responses.requests[0]["tool_choice"] == "required"
    assert responses.requests[0]["store"] is False
    openai_tool = responses.requests[0]["tools"][0]
    assert openai_tool["strict"] is True
    second_input = responses.requests[1]["input"]
    tool_output = next(
        item
        for item in second_input
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    )
    assert json.loads(tool_output["output"])["results"][0]["source"] == "vpn-access.md"
