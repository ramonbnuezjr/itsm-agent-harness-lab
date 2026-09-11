from pathlib import Path

import pytest

from harness.tools import build_search_kb_tool
from rag.ingest import load_kb
from rag.retrieve import InMemoryRetriever

KB_DIR = Path(__file__).parents[1] / "data" / "kb"


def _tool():
    return build_search_kb_tool(InMemoryRetriever(load_kb(KB_DIR)))


def test_search_kb_returns_exact_citation_label() -> None:
    result = _tool().invoke({"query": "locked account password reset"})

    assert result["results"][0]["citation"] == "[account-lockout.md]"


def test_search_kb_rejects_arguments_outside_contract() -> None:
    with pytest.raises(ValueError, match="only the required query"):
        _tool().invoke({"query": "VPN", "secret": "do not accept"})
