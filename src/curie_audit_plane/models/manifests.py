from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from curie_audit_plane.models.enums import (
    EventStatus,
    GuardrailStatus,
    HumanActionStatus,
)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence_refs: list[str] = Field(default_factory=list)


class StructuredRationale(BaseModel):
    """Auditable explanation contract. Hidden chain-of-thought is not a field."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    findings: list[Finding]
    evidence_references: list[str]
    uncertainty: str
    assumptions: list[str]
    missing_data: list[str]
    follow_up_questions: list[str]


class InputManifestItem(BaseModel):
    resource_type: str
    resource_id: str
    source_system: str
    source_location: str
    version_or_time: str | None = None
    selection_reason: str
    content_ref: str
    digest: str


class TransformationRecord(BaseModel):
    operation_id: str
    operation_name: str
    code_version: str
    parameters_digest: str
    input_refs: list[str]
    output_ref: str
    output_digest: str


class ModelManifest(BaseModel):
    model_id: str
    provider_id: str
    endpoint: str
    model_version: str
    prompt_version: str
    decoding_params: dict[str, object]
    tool_policy: str
    runtime: str
    seed: int | None = None
    requested_at: datetime | None = None
    responded_at: datetime | None = None


class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: str
    source_ref: str
    corpus_id: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    corpus_version: str | None = None
    rank: int | None = None
    score: float | None = None
    digest: str
    retrieved_at: datetime | None = None


class ToolCallRecord(BaseModel):
    tool_id: str
    tool_version: str
    argument_ref: str | None = None
    argument_digest: str | None = None
    result_ref: str | None = None
    result_digest: str | None = None
    status: EventStatus
    sequence: int
    sanitized_arguments: dict[str, object] = Field(default_factory=dict)


class GuardrailResult(BaseModel):
    rule_id: str
    rule_version: str
    scope: str
    result: GuardrailStatus
    severity: str
    message: str
    override_required: bool = False
    input_ref: str | None = None
    digest: str | None = None


class HumanActionRecord(BaseModel):
    action: HumanActionStatus
    actor: str
    role: str
    occurred_at: datetime
    comment: str = ""
    source_output_id: str
    final_output_ref: str | None = None
    final_output_digest: str | None = None
    override_policy_version: str | None = None


class IntegrityBatch(BaseModel):
    batch_id: str
    transaction_ids: list[str]
    transaction_roots: list[str]
    merkle_root: str
    signature: str
    key_id: str
    signed_at: datetime
    inclusion_index: int | None = None
    inclusion_proof: list[str] = Field(default_factory=list)
