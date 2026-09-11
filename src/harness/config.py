"""Local configuration loading without overriding deployed environment values."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_local_environment(path: str | Path = ".env") -> bool:
    """Load local development settings while preserving existing variables."""
    return load_dotenv(dotenv_path=Path(path), override=False)
