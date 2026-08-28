from enum import StrEnum


class TransactionStatus(StrEnum):
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    INCOMPLETE = "INCOMPLETE"
    TAMPERED = "TAMPERED"


class EventStatus(StrEnum):
    RECORDED = "RECORDED"
    VERIFIED = "VERIFIED"
    WARNING = "WARNING"
    FAILED = "FAILED"
    MISSING = "MISSING"
    TAMPERED = "TAMPERED"


class GuardrailStatus(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"
    ERROR = "ERROR"


class GuardrailScope(StrEnum):
    INPUT = "input"
    CONTEXT = "context"
    EVIDENCE = "evidence"
    STRUCTURED_OUTPUT = "structured_output"
    POLICY_ACTION = "policy_action"


class VerificationStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    VERIFIED = "VERIFIED"
    INCOMPLETE = "INCOMPLETE"
    FAILED = "FAILED"
    TAMPERED = "TAMPERED"


class HumanActionStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPT = "ACCEPT"
    MODIFY = "MODIFY"
    REJECT = "REJECT"


TERMINAL_HUMAN_ACTIONS = frozenset(
    {HumanActionStatus.ACCEPT, HumanActionStatus.MODIFY, HumanActionStatus.REJECT}
)


class EventType(StrEnum):
    TRANSACTION_STARTED = "transaction.started"
    INPUT_MANIFEST_CREATED = "input.manifest.created"
    TRANSFORMATION_APPLIED = "transformation.applied"
    CONTEXT_MANIFEST_CREATED = "context.manifest.created"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    MODEL_REQUESTED = "model.requested"
    MODEL_RESPONDED = "model.responded"
    STRUCTURED_OUTPUT_VALIDATED = "structured_output.validated"
    GUARDRAIL_COMPLETED = "guardrail.completed"
    HUMAN_ACTION_RECORDED = "human.action_recorded"
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_FAILED = "transaction.failed"
    INTEGRITY_PROOF_COMMITTED = "integrity.proof_committed"
    UI_ACCESS_RECORDED = "ui.access_recorded"
    EXPORT_RECORDED = "export.recorded"
    REPLAY_RECORDED = "replay.recorded"


REQUIRED_SUCCESS_EVENTS = (
    EventType.TRANSACTION_STARTED,
    EventType.INPUT_MANIFEST_CREATED,
    EventType.TRANSFORMATION_APPLIED,
    EventType.CONTEXT_MANIFEST_CREATED,
    EventType.MODEL_REQUESTED,
    EventType.MODEL_RESPONDED,
    EventType.STRUCTURED_OUTPUT_VALIDATED,
    EventType.GUARDRAIL_COMPLETED,
    EventType.HUMAN_ACTION_RECORDED,
    EventType.INTEGRITY_PROOF_COMMITTED,
    EventType.TRANSACTION_COMPLETED,
)

FORBIDDEN_PAYLOAD_METADATA_KEYS = frozenset(
    {
        "resource",
        "prompt",
        "context",
        "note",
        "chain_of_thought",
        "hidden_reasoning",
        "thinking",
    }
)
