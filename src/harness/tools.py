"""Tool contracts, knowledge-base search, and governed incident creation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from harness.actions import GovernedActionExecutor
from policies.action_contracts import IncidentPriority
from rag.retrieve import InMemoryRetriever


@dataclass(frozen=True)
class Tool:
    """A callable capability with a strict JSON-schema contract."""

    name: str
    description: str
    parameters: Mapping[str, Any]
    handler: Callable[[Mapping[str, Any]], Any]

    def invoke(self, arguments: Mapping[str, Any]) -> Any:
        return self.handler(arguments)

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": dict(self.parameters),
            "strict": True,
        }


def build_search_kb_tool(retriever: InMemoryRetriever, top_k: int = 3) -> Tool:
    """Create the governed search tool exposed to the model."""

    def search(arguments: Mapping[str, Any]) -> dict[str, Any]:
        if set(arguments) != {"query"}:
            raise ValueError("search_kb accepts only the required query argument")
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("search_kb requires a non-empty string query")

        results = retriever.search(query, top_k=top_k)
        return {
            "query": query,
            "results": [
                {
                    "source": result.chunk.source,
                    "citation": result.chunk.citation,
                    "title": result.chunk.title,
                    "excerpt": result.chunk.text,
                    "score": round(result.score, 4),
                }
                for result in results
            ],
        }

    return Tool(
        name="search_kb",
        description=(
            "Search approved ITSM knowledge-base documents for relevant procedures. "
            "Returns excerpts and exact citation labels."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A focused search query derived from the incident.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=search,
    )


CREATE_INCIDENT_DESCRIPTION = (
    "Propose creation of an ITSM incident record. The harness supplies the "
    "acting identity and any human approval; you cannot set them. High-impact "
    "proposals may be denied, which is a governed outcome and not an error. "
    "Never place credentials, passwords, tokens, or MFA codes in any field."
)

_OPTIONAL_TEXT_FIELDS = {
    "description": "Fuller description of the reported symptoms.",
    "category": "Service category, such as network or access.",
    "impact": "Reported breadth of impact.",
    "urgency": "Reported urgency.",
    "assignment_group": "Team the incident should be routed to.",
}


def _create_incident_schema() -> dict[str, Any]:
    """Build the strict JSON schema exposed for incident creation.

    OpenAI strict mode requires every declared property to appear in
    ``required``, so optional fields are declared nullable instead of omitted.
    The tool drops nulls before proposing the action.

    Returns:
        A JSON-schema object describing only creatable fields plus a reason.
    """
    properties: dict[str, Any] = {
        "short_description": {
            "type": "string",
            "description": "One-line summary of the incident.",
        },
        "reason": {
            "type": "string",
            "description": "Why this incident should be created, for the audit record.",
        },
        "priority": {
            "type": ["string", "null"],
            "enum": [member.value for member in IncidentPriority] + [None],
            "description": "Proposed priority. P1 and P2 require human approval.",
        },
    }
    for name, description in _OPTIONAL_TEXT_FIELDS.items():
        properties[name] = {"type": ["string", "null"], "description": description}
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties),
        "additionalProperties": False,
    }


def build_create_incident_tool(executor: GovernedActionExecutor) -> Tool:
    """Create the governed incident-creation tool exposed to the model.

    Args:
        executor: Governed executor holding the authenticated actor, incident
            storage, and audit logger.

    Returns:
        A :class:`Tool` that returns a structured outcome for every attempt,
        including denials, rather than raising.
    """

    def create(arguments: Mapping[str, Any]) -> dict[str, Any]:
        supplied = {
            name: value
            for name, value in (arguments or {}).items()
            if value is not None
        }
        return dict(executor.create_incident(supplied).as_tool_response())

    return Tool(
        name="create_incident",
        description=CREATE_INCIDENT_DESCRIPTION,
        parameters=_create_incident_schema(),
        handler=create,
    )
