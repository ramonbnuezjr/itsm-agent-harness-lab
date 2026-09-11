"""Governed v0.1 incident-triage loop and command-line entry point."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from harness.config import load_local_environment
from harness.logger import AuditLogger
from harness.providers import LLMProvider, ToolCallRecord
from harness.tools import build_search_kb_tool
from policies.policy_engine import CitationPolicy, PolicyCheck
from rag.ingest import load_kb
from rag.retrieve import InMemoryRetriever

AGENT_INSTRUCTIONS = """You are an ITSM triage assistant.
Use search_kb before recommending a next step. Base recommendations only on the
returned excerpts. Cite at least one returned source using its exact label, such
as [vpn-access.md]. If the KB does not support a recommendation, say so and
recommend human review. Do not claim that you performed any remediation.
"""

BLOCKED_RESPONSE = (
    "Recommendation withheld: the generated response did not satisfy the "
    "approved knowledge-base citation policy. Escalate to a human reviewer."
)


@dataclass(frozen=True)
class RunResult:
    output: str
    policy_checks: tuple[PolicyCheck, ...]
    tool_calls: tuple[ToolCallRecord, ...]
    audit_event_id: str


class AgentHarness:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        retriever: InMemoryRetriever,
        audit_logger: AuditLogger,
    ) -> None:
        self.provider = provider
        self.search_tool = build_search_kb_tool(retriever)
        self.audit_logger = audit_logger
        self.citation_policy = CitationPolicy()

    def run(self, incident: str) -> RunResult:
        if not incident.strip():
            raise ValueError("Incident description must not be empty")

        model_result = self.provider.run(
            user_input=incident,
            instructions=AGENT_INSTRUCTIONS,
            tools=[self.search_tool],
            require_tool=True,
        )
        approved_sources = _approved_sources(model_result.tool_calls)
        citation_check = self.citation_policy.evaluate(
            model_result.output, approved_sources
        )
        final_output = model_result.output if citation_check.passed else BLOCKED_RESPONSE
        event_id = self.audit_logger.append(
            {
                "incident_input": incident,
                "tool_calls": [
                    {
                        "name": call.name,
                        "arguments": call.arguments,
                        "output": call.output,
                    }
                    for call in model_result.tool_calls
                ],
                "model_output": model_result.output,
                "final_output": final_output,
                "policy_checks": [citation_check.as_dict()],
            }
        )
        return RunResult(
            output=final_output,
            policy_checks=(citation_check,),
            tool_calls=model_result.tool_calls,
            audit_event_id=event_id,
        )


def _approved_sources(tool_calls: tuple[ToolCallRecord, ...]) -> set[str]:
    sources: set[str] = set()
    for call in tool_calls:
        if call.name != "search_kb" or not isinstance(call.output, dict):
            continue
        results = call.output.get("results", [])
        if not isinstance(results, list):
            continue
        for result in results:
            if isinstance(result, dict) and isinstance(result.get("source"), str):
                sources.add(result["source"])
    return sources


def main() -> None:
    load_local_environment()
    parser = argparse.ArgumentParser(description="Run governed ITSM incident triage")
    parser.add_argument("incident", help="Incident description to triage")
    parser.add_argument(
        "--kb-dir",
        type=Path,
        default=Path("data/kb"),
        help="Directory containing approved Markdown KB documents",
    )
    parser.add_argument(
        "--audit-log",
        type=Path,
        default=Path("var/audit.jsonl"),
        help="Append-only JSONL audit log path",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        help="OpenAI model ID (default: OPENAI_MODEL or gpt-4o-mini)",
    )
    args = parser.parse_args()

    from harness.providers import OpenAIProvider

    harness = AgentHarness(
        provider=OpenAIProvider(model=args.model),
        retriever=InMemoryRetriever(load_kb(args.kb_dir)),
        audit_logger=AuditLogger(args.audit_log),
    )
    result = harness.run(args.incident)
    print(result.output)
    print(f"\nAudit event: {result.audit_event_id}")


if __name__ == "__main__":
    main()
