from curie_audit_plane.models.enums import (
    EventStatus,
    EventType,
    GuardrailStatus,
    HumanActionStatus,
    TransactionStatus,
    VerificationStatus,
)
from curie_audit_plane.models.manifests import StructuredRationale


def test_event_types_match_prd_dotted_names():
    assert EventType.TRANSACTION_STARTED == "transaction.started"
    assert EventType.INPUT_MANIFEST_CREATED == "input.manifest.created"
    assert EventType.TRANSFORMATION_APPLIED == "transformation.applied"
    assert EventType.CONTEXT_MANIFEST_CREATED == "context.manifest.created"
    assert EventType.RETRIEVAL_COMPLETED == "retrieval.completed"
    assert EventType.TOOL_CALLED == "tool.called"
    assert EventType.TOOL_COMPLETED == "tool.completed"
    assert EventType.MODEL_REQUESTED == "model.requested"
    assert EventType.MODEL_RESPONDED == "model.responded"
    assert EventType.STRUCTURED_OUTPUT_VALIDATED == "structured_output.validated"
    assert EventType.GUARDRAIL_COMPLETED == "guardrail.completed"
    assert EventType.HUMAN_ACTION_RECORDED == "human.action_recorded"
    assert EventType.TRANSACTION_COMPLETED == "transaction.completed"
    assert EventType.TRANSACTION_FAILED == "transaction.failed"
    assert EventType.INTEGRITY_PROOF_COMMITTED == "integrity.proof_committed"
    assert EventType.REPLAY_RECORDED == "replay.recorded"


def test_transaction_statuses_are_prd_family():
    assert {status.value for status in TransactionStatus} == {
        "STARTED",
        "RUNNING",
        "WAITING_FOR_REVIEW",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "INCOMPLETE",
        "TAMPERED",
    }


def test_event_guardrail_verification_and_human_statuses_match_prd():
    assert {status.value for status in EventStatus} == {
        "RECORDED",
        "VERIFIED",
        "WARNING",
        "FAILED",
        "MISSING",
        "TAMPERED",
    }
    assert {status.value for status in GuardrailStatus} == {"PASS", "WARN", "BLOCK", "ERROR"}
    assert {status.value for status in VerificationStatus} == {
        "NOT_RUN",
        "VERIFIED",
        "INCOMPLETE",
        "FAILED",
        "TAMPERED",
    }
    assert {status.value for status in HumanActionStatus} == {
        "PENDING",
        "ACCEPT",
        "MODIFY",
        "REJECT",
    }


def test_structured_rationale_has_no_hidden_reasoning_fields():
    fields = set(StructuredRationale.model_fields)
    assert "chain_of_thought" not in fields
    assert "hidden_reasoning" not in fields
    assert "thinking" not in fields
    for required in (
        "summary",
        "findings",
        "evidence_references",
        "uncertainty",
        "assumptions",
        "missing_data",
        "follow_up_questions",
    ):
        assert required in fields
