"""Load approved Markdown knowledge-base documents."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    title: str
    text: str

    @property
    def citation(self) -> str:
        return f"[{self.source}]"


def load_kb(kb_dir: str | Path) -> list[KnowledgeChunk]:
    """Load each Markdown file as one deterministic v0.1 retrieval chunk."""
    directory = Path(kb_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Knowledge-base directory not found: {directory}")

    chunks: list[KnowledgeChunk] = []
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        first_line = text.splitlines()[0]
        title = first_line.lstrip("# ").strip() or path.stem.replace("-", " ").title()
        chunks.append(KnowledgeChunk(source=path.name, title=title, text=text))

    if not chunks:
        raise ValueError(f"No non-empty Markdown documents found in {directory}")
    return chunks
