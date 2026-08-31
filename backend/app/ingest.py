from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from .models import Event


@dataclass
class IngestResult:
    accepted: bool
    duplicate: bool
    reason: str


class EventIngestor:
    """In-memory ingestion boundary for the MVP; PostgreSQL persistence comes next."""

    def __init__(self) -> None:
        self._event_ids: Dict[str, Event] = {}

    def ingest(self, event: Event) -> IngestResult:
        # Authenticate before consuming the event ID namespace. An unverified
        # webhook must never reserve an ID and block a later valid delivery.
        if not event.signature_verified:
            return IngestResult(accepted=False, duplicate=False, reason="signature_verification_failed")
        if event.event_id in self._event_ids:
            return IngestResult(accepted=False, duplicate=True, reason="duplicate_event_id")
        self._event_ids[event.event_id] = event
        return IngestResult(accepted=True, duplicate=False, reason="accepted")

    def all_events_for(self, transaction_id: str) -> Tuple[Event, ...]:
        return tuple(e for e in self._event_ids.values() if e.transaction_id == transaction_id)
