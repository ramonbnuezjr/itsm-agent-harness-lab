import json
from pathlib import Path
from typing import Sequence

from harness.logger import AuditLogger
from harness.loop import AgentHarness, BLOCKED_RESPONSE
from harness.providers import ModelResult, ToolCallRecord
from harness.tools import Tool
from rag.ingest import load_kb
from rag.retrieve import InMemoryRetriever

KB_DIR = Path(__file__).parents[1] / "data" / "kb"


class FakeProvider:
    def __init__(self, *, include_citation: bool) -> None:
        self.include_citation = include_citation

    def run(
        self,
        *,
        user_input: str,
        instructions: str,
        tools: Sequence[Tool],
        require_tool: bool = False,
    ) -> ModelResult:
        assert require_tool
        result = tools[0].invoke({"query": user_input})
        citation = result["results"][0]["citation"]
        output = "Restart the VPN client."
        if self.include_citation:
            output = f"Restart the VPN client and retry {citation}."
        return ModelResult(
            output=output,
            tool_calls=(
                ToolCallRecord(
                    name="search_kb",
                    arguments={"query": user_input},
                    output=result,
                ),
            ),
        )


def _harness(tmp_path: Path, *, include_citation: bool) -> AgentHarness:
    return AgentHarness(
        provider=FakeProvider(include_citation=include_citation),
        retriever=InMemoryRetriever(load_kb(KB_DIR)),
        audit_logger=AuditLogger(tmp_path / "audit.jsonl"),
    )


def test_harness_returns_governed_response_and_writes_audit_log(tmp_path: Path) -> None:
    harness = _harness(tmp_path, include_citation=True)

    result = harness.run("VPN client cannot connect to the gateway")

    assert result.policy_checks[0].passed
    assert "[vpn-access.md]" in result.output
    record = json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8"))
    assert record["event_id"] == result.audit_event_id
    assert record["tool_calls"][0]["name"] == "search_kb"
    assert record["policy_checks"][0]["passed"] is True


def test_harness_withholds_response_that_fails_policy(tmp_path: Path) -> None:
    harness = _harness(tmp_path, include_citation=False)

    result = harness.run("VPN client cannot connect to the gateway")

    assert result.output == BLOCKED_RESPONSE
    assert not result.policy_checks[0].passed
