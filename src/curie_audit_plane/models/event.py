from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from curie_audit_plane.models.enums import (
    FORBIDDEN_PAYLOAD_METADATA_KEYS,
    EventStatus,
    EventType,
)


class AuditEventRecord(BaseModel):
    schema_version: str = "1.0.0"
    producer_version: str = "0.1.0"
    event_id: str
    transaction_id: str
    sequence_number: int
    event_type: EventType
    actor_service: str
    occurred_at: datetime
    status: EventStatus = EventStatus.RECORDED
    payload_ref: str | None = None
    payload_digest: str | None = None
    payload_metadata: dict[str, object] = Field(default_factory=dict)
    previous_event_hash: str = ""
    event_hash: str = ""

    @field_validator("payload_metadata")
    @classmethod
    def reject_clinical_payload_keys(cls, value: dict[str, object]) -> dict[str, object]:
        forbidden = FORBIDDEN_PAYLOAD_METADATA_KEYS.intersection(value)
        if forbidden:
            raise ValueError(
                "payload_metadata must not contain clinical or hidden-reasoning keys: "
                + ", ".join(sorted(forbidden))
            )
        return value
