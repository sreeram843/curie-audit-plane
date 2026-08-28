from datetime import datetime

from pydantic import BaseModel, Field

from curie_audit_plane.models.enums import (
    HumanActionStatus,
    TransactionStatus,
    VerificationStatus,
)


class VerificationReport(BaseModel):
    status: VerificationStatus
    scope: list[str]
    chain_ok: bool
    merkle_ok: bool
    signature_ok: bool
    key_id: str
    verified_at: datetime
    missing_events: list[str] = Field(default_factory=list)
    hash_failures: list[str] = Field(default_factory=list)
    reason: str = ""
    content_ok: bool = True


class ReplayClassification(BaseModel):
    result: str  # EXACT_MATCH | EQUIVALENT | DIVERGENT | NOT_REPLAYABLE
    original_digest: str
    replay_digest: str
    reasons: list[str] = Field(default_factory=list)
    replay_content_ref: str | None = None
    original_output: dict | None = None
    modified_output: dict | None = None
    replay_output: dict | None = None
    original_event_id: str | None = None
    modified_event_id: str | None = None


class TransactionOverview(BaseModel):
    transaction_id: str
    purpose: str
    subject_ref: str
    status: TransactionStatus
    verification_status: VerificationStatus
    human_action: HumanActionStatus
    started_at: datetime
    ended_at: datetime | None = None
    event_count: int
    missing_event_count: int
    failed_event_count: int
    schema_version: str = "1.0.0"
