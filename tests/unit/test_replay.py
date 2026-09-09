from curie_audit_plane.adapters.completion import CompletionRequest, complete_stub
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.replay import classify_replay_outputs, finalize_replay_result
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def _pipeline(tmp_path) -> Pipeline:
    private_key, public_key = generate_keypair()
    return Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        )
    )


def test_replay_exact_equivalent_and_divergent(tmp_path):
    exact = _pipeline(tmp_path / "exact")
    original = exact.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    replay = exact.replay(original.transaction.transaction_id)
    assert replay.result == "EXACT_MATCH"
    assert replay.replay_content_ref
    assert replay.original_output["summary"]
    assert replay.replay_output["summary"]
    assert replay.original_event_id
    assert replay.modified_output is None

    request = CompletionRequest(
        context_digest="d",
        context=[],
        evidence_ids=["obs-bp-TEST-00001"],
        prompt_version="clinical-summary.v1",
    )
    stub = complete_stub(request)
    equivalent, eq_reasons = classify_replay_outputs(
        stub.output,
        stub.output.model_copy(update={"summary": stub.output.summary + " "}),
    )
    assert equivalent == "EQUIVALENT"
    assert eq_reasons
    divergent, div_reasons = classify_replay_outputs(
        stub.output,
        stub.output.model_copy(update={"summary": "Materially different summary."}),
    )
    assert divergent == "DIVERGENT"
    assert "summary differs" in div_reasons


def test_hosted_model_replay_is_never_exact_match():
    result, reasons = finalize_replay_result(
        runtime="openai-compatible",
        endpoint="http://127.0.0.1:1234/v1",
        classification="EXACT_MATCH",
        reasons=[],
    )
    assert result == "EQUIVALENT"
    assert any("not bit-exact" in reason or "hosted" in reason.lower() for reason in reasons)
    missing, missing_reasons = finalize_replay_result(
        runtime="openai-compatible",
        endpoint="",
        classification="EXACT_MATCH",
        reasons=[],
    )
    assert missing == "NOT_REPLAYABLE"
    assert missing_reasons


def test_pipeline_hosted_replay_is_equivalent_or_not_replayable(tmp_path, monkeypatch):
    import json

    from curie_audit_plane.adapters.completion import complete_stub
    from curie_audit_plane.models.enums import EventType

    pipeline = _pipeline(tmp_path / "hosted")
    original = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    tx_id = original.transaction.transaction_id
    model = next(event for event in original.events if event.event_type == EventType.MODEL_REQUESTED)

    def _rewrite(runtime: str, endpoint: str) -> None:
        updated = model.model_copy(
            update={"payload_metadata": {**model.payload_metadata, "runtime": runtime, "endpoint": endpoint}}
        )
        pipeline.services.audit._conn.execute(
            "UPDATE events SET event_json = ? WHERE event_id = ?",
            (json.dumps(updated.model_dump(mode="json")), model.event_id),
        )
        pipeline.services.audit._conn.commit()

    replayed_models = []

    def fake_openai(request, **kwargs):
        replayed_models.append(kwargs["model"])
        return complete_stub(request)

    monkeypatch.setattr("curie_audit_plane.pipeline.complete_openai_compatible", fake_openai)
    _rewrite("openai-compatible", "http://127.0.0.1:1234/v1")
    matching = pipeline.replay(tx_id, model_id="curie-hosted-substitute")
    assert matching.result == "EQUIVALENT"
    assert any("not bit-exact" in reason or "hosted" in reason.lower() for reason in matching.reasons)
    assert replayed_models == ["curie-hosted-substitute"]

    _rewrite("openai-compatible", "")
    missing = pipeline.replay(tx_id)
    assert missing.result == "NOT_REPLAYABLE"
