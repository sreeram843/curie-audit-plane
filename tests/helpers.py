from curie_audit_plane.models.event import AuditEventRecord


def make_event(**overrides) -> AuditEventRecord:
    payload = {
        "schema_version": "1.0.0",
        "producer_version": "0.1.0",
        "event_id": "evt-1",
        "transaction_id": "tx-1",
        "sequence_number": 0,
        "event_type": "transaction.started",
        "actor_service": "curie-audit-plane",
        "occurred_at": "2026-08-27T17:00:00+00:00",
        "status": "RECORDED",
        "payload_ref": None,
        "payload_digest": None,
        "payload_metadata": {"purpose": "synthetic-encounter-summary"},
        "previous_event_hash": "",
        "event_hash": "",
    }
    payload.update(overrides)
    return AuditEventRecord.model_validate(payload)
