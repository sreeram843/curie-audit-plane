from curie_audit_plane.evaluation.benchmark import run_benchmark
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def test_arc_and_tamper_detection_meet_prototype_targets(tmp_path):
    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        )
    )
    report = run_benchmark(pipeline)
    assert report.clean_arc >= 0.95
    assert report.silent_missing_fields == 0
    assert report.tamper_detection_rate == 1.0
    assert report.false_tamper_rate == 0.0
    assert report.clean_case_count >= 3
    assert report.required_event_completeness == 1.0
    names = {case["name"] for case in report.cases}
    assert names >= {
        "clean",
        "missing_event",
        "missing_input",
        "missing_transformation",
        "missing_evidence",
        "missing_tool",
        "missing_guardrail",
        "changed_timestamp",
        "reviewer_action",
        "wrong_corpus",
        "wrong_content_ref",
        "wrong_corpus_rehashed",
        "wrong_content_ref_rehashed",
        "replay_stub",
        "proof_substitution",
        "mutate",
        "delete",
        "reorder",
        "broken_reference",
        "bad_merkle",
        "bad_signature",
    }
    rehashed_corpus = next(case for case in report.cases if case["name"] == "wrong_corpus_rehashed")
    rehashed_content = next(case for case in report.cases if case["name"] == "wrong_content_ref_rehashed")
    assert rehashed_corpus["chain_ok"] is True
    assert rehashed_content["chain_ok"] is True
    assert rehashed_corpus["content_ok"] is False or rehashed_corpus["detected"]
    assert rehashed_content["content_ok"] is False
    replay = next(case for case in report.cases if case["name"] == "replay_stub")
    assert replay["kind"] == "replay"
    assert replay["result"] in {"EXACT_MATCH", "EQUIVALENT", "DIVERGENT", "NOT_REPLAYABLE"}
    tamper_cases = [case for case in report.cases if case["kind"] == "tamper"]
    assert all(case["detected"] for case in tamper_cases)

