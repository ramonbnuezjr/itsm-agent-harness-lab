"""Tool contracts and the v0.1 knowledge-base search tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

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
