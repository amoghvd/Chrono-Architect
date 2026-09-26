from __future__ import annotations

from pathlib import Path
from threading import Lock

from .models import AuditEvent, RunState
from .policy import sha256


class AuditLog:
    """Per-run append-only, hash-chained JSONL audit log."""
    def __init__(self, directory: Path):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, run_id: str, kind: str, data: dict | None = None,
               state: RunState | None = None) -> AuditEvent:
        path = self.directory / f"{run_id}.jsonl"
        with self._lock:
            events = self.read(run_id)
            event = AuditEvent(
                sequence=len(events) + 1,
                run_id=run_id,
                kind=kind,
                state=state,
                data=data or {},
                previous_event_hash=events[-1].event_hash if events else None,
            )
            event = event.model_copy(update={"event_hash": sha256(event)})
            with path.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
            return event

    def read(self, run_id: str) -> list[AuditEvent]:
        path = self.directory / f"{run_id}.jsonl"
        if not path.exists():
            return []
        return [AuditEvent.model_validate_json(line) for line in path.read_text().splitlines() if line]

    def verify(self, run_id: str) -> bool:
        previous = None
        for event in self.read(run_id):
            if event.previous_event_hash != previous:
                return False
            expected = sha256(event.model_copy(update={"event_hash": None}))
            if event.event_hash != expected:
                return False
            previous = event.event_hash
        return True
