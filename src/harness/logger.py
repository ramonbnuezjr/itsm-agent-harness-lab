"""Append-only JSONL audit logging."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: Mapping[str, Any]) -> str:
        """Write one complete audit event and return its identifier."""
        event_id = str(uuid4())
        record = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as audit_file:
            audit_file.write(json.dumps(record, sort_keys=True) + "\n")
        return event_id
