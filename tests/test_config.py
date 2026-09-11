import os
from pathlib import Path

from harness.config import load_local_environment


def test_load_local_environment_reads_dotenv(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=test-value\n", encoding="utf-8")

    loaded = load_local_environment(dotenv_path)

    assert loaded
    assert os.environ["OPENAI_API_KEY"] == "test-value"


def test_load_local_environment_does_not_override_existing_value(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "deployed-value")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("OPENAI_API_KEY=local-value\n", encoding="utf-8")

    load_local_environment(dotenv_path)

    assert os.environ["OPENAI_API_KEY"] == "deployed-value"
