"""Small, auditable policy checks for v0.1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable


@dataclass(frozen=True)
class PolicyCheck:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class CitationPolicy:
    """Require a citation to a source returned by the approved KB tool."""

    name = "recommendations_require_approved_kb_citation"

    def evaluate(self, output: str, approved_sources: Iterable[str]) -> PolicyCheck:
        sources = sorted(set(approved_sources))
        cited_sources = [source for source in sources if f"[{source}]" in output]
        if cited_sources:
            return PolicyCheck(
                name=self.name,
                passed=True,
                detail=f"Approved citation found: {cited_sources[0]}",
            )
        if not sources:
            detail = "No approved KB sources were returned by search_kb."
        else:
            detail = "Recommendation did not cite a source returned by search_kb."
        return PolicyCheck(name=self.name, passed=False, detail=detail)
