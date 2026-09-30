import json
from pathlib import Path

import pytest

from curie_audit_plane.adapters.completion import complete_stub
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import (
    EventType,
    GuardrailStatus,
    HumanActionStatus,
    TransactionStatus,
    VerificationStatus,
)
from curie_audit_plane.models.manifests import Finding, StructuredRationale
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def _pipeline(tmp_path: Path) -> Pipeline:
    private_key, public_key = generate_keypair()
    services = PipelineServices(
        audit=AuditStore(tmp_path / "audit.sqlite"),
        content=ProtectedContentStore(tmp_path / "protected"),
        private_key=private_key,
        public_key=public_key,
        key_id="test-key",
    )
    return Pipeline(services)


def test_full_synthetic_transaction_records_required_events(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    types = [event.event_type for event in result.events]
    for required in (
        EventType.TRANSACTION_STARTED,
        EventType.INPUT_MANIFEST_CREATED,
        EventType.TRANSFORMATION_APPLIED,
        EventType.CONTEXT_MANIFEST_CREATED,
        EventType.RETRIEVAL_COMPLETED,
        EventType.TOOL_CALLED,
        EventType.MODEL_REQUESTED,
        EventType.MODEL_RESPONDED,
        EventType.STRUCTURED_OUTPUT_VALIDATED,
        EventType.GUARDRAIL_COMPLETED,
        EventType.HUMAN_ACTION_RECORDED,
        EventType.INTEGRITY_PROOF_COMMITTED,
        EventType.TRANSACTION_COMPLETED,
    ):
        assert required in types
    assert result.transaction.status == TransactionStatus.COMPLETED
    assert result.verification.status == VerificationStatus.VERIFIED
    for event in result.events:
        if event.payload_ref:
            payload = pipeline.services.content.get(event.payload_ref)
            assert event.payload_digest
            assert "resourceType" not in event.payload_metadata
            assert payload


def test_accept_modify_and_reject_each_record_terminal_disposition(tmp_path):
    for action in (HumanActionStatus.ACCEPT, HumanActionStatus.MODIFY, HumanActionStatus.REJECT):
        pipeline = _pipeline(tmp_path / action.value)
        modified = None
        if action == HumanActionStatus.MODIFY:
            modified = StructuredRationale(
                summary="Clinician-adjusted summary.",
                findings=[Finding(text="BP remains high", evidence_refs=["obs-bp-TEST-00001"])],
                evidence_references=["obs-bp-TEST-00001"],
                uncertainty="Home readings still missing.",
                assumptions=[],
                missing_data=["Home BP"],
                follow_up_questions=[],
            )
        result = pipeline.run_transaction(
            human_action=action,
            actor="reviewer@curie.local",
            modified_output=modified,
            comment="reviewed",
        )
        human = next(event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED)
        assert human.payload_metadata["action"] == action.value
        assert result.transaction.human_action == action


def test_blocked_output_cannot_be_accepted_without_override(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
        force_guardrail=GuardrailStatus.BLOCK,
    )
    assert result.transaction.status == TransactionStatus.BLOCKED
    assert result.transaction.human_action == HumanActionStatus.PENDING
    assert EventType.HUMAN_ACTION_RECORDED not in {event.event_type for event in result.events}


def test_empty_bundle_fails_closed(tmp_path):
    pipeline = _pipeline(tmp_path)
    empty = tmp_path / "empty-bundle.json"
    empty.write_text(json.dumps({"resourceType": "Bundle", "type": "collection", "entry": []}), encoding="utf-8")
    pipeline.fixture_path = empty
    result = pipeline.run_transaction(actor="reviewer@curie.local")
    assert result.transaction.status == TransactionStatus.FAILED
    assert result.transaction.ended_at is not None
    assert EventType.TRANSACTION_FAILED in {event.event_type for event in result.events}


def test_phi_in_review_comment_is_redacted(tmp_path):
    pipeline = _pipeline(tmp_path)
    waiting = pipeline.run_transaction(actor="reviewer@curie.local")
    result = pipeline.record_human_action(
        waiting.transaction.transaction_id,
        action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
        comment="Reviewed Patient TEST-00001 in clinic.",
    )
    human = next(event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED)
    assert human.payload_metadata["comment"] == ""
    assert human.payload_metadata["comment_redacted"] is True
    assert human.payload_metadata["comment_present"] is True
    assert "TEST-00001" not in str(human.payload_metadata)


def test_replay_uses_recorded_stub_runtime_not_current_completer(tmp_path):
    from curie_audit_plane.adapters.completion import (
        CompletionRequest,
        CompletionResult,
        complete_stub,
    )
    from curie_audit_plane.integrity.canonical import canonicalize
    from curie_audit_plane.integrity.hashing import sha256_hex

    pipeline = _pipeline(tmp_path)
    original = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")

    def diverge(request: CompletionRequest) -> CompletionResult:
        base = complete_stub(request)
        output = base.output.model_copy(update={"summary": "Materially different summary."})
        digest = sha256_hex(canonicalize(output.model_dump(mode="json")))
        return CompletionResult(
            output=output,
            manifest=base.manifest,
            request_digest=base.request_digest,
            response_digest=digest,
            token_usage=base.token_usage,
        )

    pipeline.completer = diverge
    replay = pipeline.replay(original.transaction.transaction_id)
    assert replay.result == "EXACT_MATCH"


def test_replay_with_prompt_v2_is_divergent_on_stub(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
        prompt_version="clinical-summary.v1",
    )
    replayed = pipeline.replay(
        result.transaction.transaction_id,
        prompt_version="clinical-summary.v2",
    )
    assert replayed.result == "DIVERGENT"
    assert "summary differs" in replayed.reasons
    access = pipeline.services.audit.list_access_events(result.transaction.transaction_id)
    assert any(event.event_type == EventType.REPLAY_RECORDED for event in access)
    loaded = pipeline.load_result(result.transaction.transaction_id)
    assert loaded.verification.status == VerificationStatus.VERIFIED
    pipeline.close()


def test_pipeline_rejects_pending_as_terminal_disposition(tmp_path):
    pipeline = _pipeline(tmp_path)
    with pytest.raises(ValueError, match="PENDING"):
        pipeline.run_transaction(
            human_action=HumanActionStatus.PENDING,
            actor="reviewer@curie.local",
        )
    waiting = pipeline.run_transaction(actor="reviewer@curie.local")
    assert waiting.transaction.status == TransactionStatus.WAITING_FOR_REVIEW
    assert waiting.transaction.human_action == HumanActionStatus.PENDING
    with pytest.raises(ValueError, match="PENDING"):
        pipeline.record_human_action(
            waiting.transaction.transaction_id,
            action=HumanActionStatus.PENDING,
            actor="reviewer@curie.local",
        )


def test_replay_of_stub_is_exact(tmp_path):
    pipeline = _pipeline(tmp_path)
    original = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    replay = pipeline.replay(original.transaction.transaction_id)
    assert replay.result == "EXACT_MATCH"
    assert replay.original_digest == replay.replay_digest
    assert replay.replay_content_ref


def test_transaction_failure_is_recorded_for_invalid_fixture(tmp_path):
    pipeline = _pipeline(tmp_path)
    pipeline.fixture_path = tmp_path / "missing.json"
    result = pipeline.run_transaction(actor="reviewer@curie.local")
    assert result.transaction.status == TransactionStatus.FAILED
    assert result.transaction.ended_at is not None
    assert EventType.TRANSACTION_FAILED in {event.event_type for event in result.events}
    assert result.verification.status in {VerificationStatus.FAILED, VerificationStatus.INCOMPLETE}


def test_forced_adapter_failure_does_not_leave_running(tmp_path):
    pipeline = _pipeline(tmp_path)

    def boom(_request):
        raise RuntimeError("adapter exploded")

    pipeline.completer = boom
    result = pipeline.run_transaction(actor="reviewer@curie.local")
    assert result.transaction.status == TransactionStatus.FAILED
    failed = next(event for event in result.events if event.event_type == EventType.TRANSACTION_FAILED)
    assert failed.payload_metadata["error_code"] == "RuntimeError"
    assert result.events[-1].event_hash


def test_adapter_exception_text_is_not_stored_on_the_audit_chain(tmp_path):
    pipeline = _pipeline(tmp_path)

    def boom(_request):
        raise RuntimeError("provider echoed Patient TEST-00001 and 123-45-6789")

    pipeline.completer = boom
    result = pipeline.run_transaction(actor="reviewer@curie.local")
    assert result.transaction.status == TransactionStatus.FAILED
    failed = next(event for event in result.events if event.event_type == EventType.TRANSACTION_FAILED)
    meta = json.dumps(failed.payload_metadata)
    assert failed.payload_metadata["error_code"] == "RuntimeError"
    assert "TEST-00001" not in meta
    assert "123-45-6789" not in meta
    assert "provider echoed" not in meta
    assert failed.payload_metadata.get("message") in {"", None}
    assert "message_digest" not in failed.payload_metadata


def test_transformation_events_include_full_record(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    transforms = [event for event in result.events if event.event_type == EventType.TRANSFORMATION_APPLIED]
    for event in transforms:
        for field in (
            "operation_id",
            "operation_name",
            "code_version",
            "parameters_digest",
            "input_refs",
            "output_ref",
            "output_digest",
        ):
            assert event.payload_metadata.get(field)
    context = next(event for event in result.events if event.event_type == EventType.CONTEXT_MANIFEST_CREATED)
    last = transforms[-1]
    assert last.payload_metadata["output_ref"] == context.payload_ref


def test_sealed_transaction_rejects_clinical_append(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    extra = result.events[-1].model_copy(update={"event_id": "extra", "sequence_number": 99})
    with pytest.raises(ValueError, match="sealed"):
        pipeline.services.audit.append_event(extra)


def test_recorded_and_unrecorded_share_one_clinical_completion_request(tmp_path):
    requests = []

    def tracking_completer(request):
        requests.append(request)
        return complete_stub(request)

    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        ),
        completer=tracking_completer,
    )
    unrecorded = pipeline.run_unrecorded_workflow(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
    )
    recorded = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
    )

    assert len(requests) == 2
    assert requests[0].context_digest == requests[1].context_digest
    assert requests[0].prompt_version == requests[1].prompt_version
    assert requests[0].model_id == requests[1].model_id
    assert requests[0].evidence_ids == requests[1].evidence_ids
    assert unrecorded["output"].model_dump() == recorded.output.model_dump()


def test_unrecorded_workflow_includes_in_memory_accept_without_audit_events(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_unrecorded_workflow(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
    )
    stages = [record["stage"] for record in result["records"]]
    assert stages == [
        "load",
        "transform",
        "context",
        "retrieve",
        "complete",
        "guardrail",
        "review",
    ]
    review = result["records"][-1]
    assert review["action"] == HumanActionStatus.ACCEPT.value
    assert review["actor"] == "reviewer@curie.local"
    assert review["final_output_digest"]
    assert pipeline.services.audit.list_transactions() == []
