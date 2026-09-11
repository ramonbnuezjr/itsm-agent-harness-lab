from pathlib import Path

from rag.ingest import load_kb
from rag.retrieve import InMemoryRetriever

KB_DIR = Path(__file__).parents[1] / "data" / "kb"


def test_load_kb_is_deterministic() -> None:
    chunks = load_kb(KB_DIR)

    assert [chunk.source for chunk in chunks] == sorted(chunk.source for chunk in chunks)
    assert len(chunks) == 4


def test_retrieve_returns_relevant_vpn_document_first() -> None:
    retriever = InMemoryRetriever(load_kb(KB_DIR))

    results = retriever.search("VPN client cannot connect to gateway")

    assert results
    assert results[0].chunk.source == "vpn-access.md"
    assert results[0].chunk.citation == "[vpn-access.md]"


def test_retrieve_returns_no_results_for_unrelated_query() -> None:
    retriever = InMemoryRetriever(load_kb(KB_DIR))

    assert retriever.search("orchid greenhouse humidity") == []
