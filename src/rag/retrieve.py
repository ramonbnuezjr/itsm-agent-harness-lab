"""Deterministic in-memory retrieval using term-frequency cosine similarity."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from rag.ingest import KnowledgeChunk

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SearchResult:
    chunk: KnowledgeChunk
    score: float


def _tokens(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    numerator = sum(count * right.get(token, 0) for token, count in left.items())
    if numerator == 0:
        return 0.0
    left_norm = math.sqrt(sum(count * count for count in left.values()))
    right_norm = math.sqrt(sum(count * count for count in right.values()))
    return numerator / (left_norm * right_norm)


class InMemoryRetriever:
    """A transparent retrieval baseline suitable for the small v0.1 KB."""

    def __init__(self, chunks: Iterable[KnowledgeChunk]) -> None:
        self._chunks = tuple(chunks)
        if not self._chunks:
            raise ValueError("Retriever requires at least one knowledge chunk")
        self._vectors = {
            chunk.source: Counter(_tokens(f"{chunk.title} {chunk.title} {chunk.text}"))
            for chunk in self._chunks
        }

    def search(self, query: str, *, top_k: int = 3) -> list[SearchResult]:
        if not query.strip():
            raise ValueError("Query must not be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")

        query_vector = Counter(_tokens(query))
        results = [
            SearchResult(chunk=chunk, score=_cosine(query_vector, self._vectors[chunk.source]))
            for chunk in self._chunks
        ]
        relevant = [result for result in results if result.score > 0]
        return sorted(
            relevant,
            key=lambda result: (-result.score, result.chunk.source),
        )[:top_k]
