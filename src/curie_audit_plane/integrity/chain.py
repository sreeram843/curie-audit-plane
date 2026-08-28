from dataclasses import dataclass, field

from curie_audit_plane.integrity.hashing import GENESIS_HASH, hash_event
from curie_audit_plane.models.event import AuditEventRecord


@dataclass
class ChainReport:
    ok: bool
    reason: str = ""
    hash_failures: list[str] = field(default_factory=list)


def link_chain(events: list[AuditEventRecord]) -> list[AuditEventRecord]:
    previous = GENESIS_HASH
    linked: list[AuditEventRecord] = []
    for event in events:
        updated = event.model_copy(update={"previous_event_hash": previous, "event_hash": ""})
        digest = hash_event(updated.model_dump(mode="json"))
        updated = updated.model_copy(update={"event_hash": digest})
        linked.append(updated)
        previous = digest
    return linked


def verify_chain(events: list[AuditEventRecord]) -> ChainReport:
    if not events:
        return ChainReport(ok=False, reason="empty event sequence")
    previous = GENESIS_HASH
    failures: list[str] = []
    for index, event in enumerate(events):
        if event.sequence_number != index:
            return ChainReport(
                ok=False,
                reason=f"sequence number {event.sequence_number} is out of order at index {index}",
                hash_failures=failures,
            )
        if event.previous_event_hash != previous:
            return ChainReport(
                ok=False,
                reason="broken previous_event_hash link",
                hash_failures=failures + [event.event_id],
            )
        expected = hash_event(event.model_dump(mode="json"))
        if expected != event.event_hash:
            failures.append(event.event_id)
        previous = event.event_hash
    if failures:
        return ChainReport(ok=False, reason="event hash mismatch", hash_failures=failures)
    return ChainReport(ok=True)


def per_event_hash_statuses(events: list[AuditEventRecord]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    previous = GENESIS_HASH
    for index, event in enumerate(events):
        expected = hash_event(event.model_dump(mode="json"))
        if expected != event.event_hash:
            statuses[event.event_id] = "TAMPERED"
        elif event.sequence_number != index or event.previous_event_hash != previous:
            statuses[event.event_id] = "FAILED"
        else:
            statuses[event.event_id] = "VERIFIED"
        previous = event.event_hash
    return statuses
