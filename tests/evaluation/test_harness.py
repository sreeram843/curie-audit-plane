from curie_audit_plane.evaluation.harness import run_evaluation_harness
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def test_evaluation_harness_reports_baselines_overhead_and_reviewer_task(tmp_path):
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
    report = run_evaluation_harness(pipeline)
    names = {item["name"] for item in report.baselines}
    assert names >= {"application_log", "hash_only", "fhir_projection", "complete_plane"}
    complete = next(item for item in report.baselines if item["name"] == "complete_plane")
    logs = next(item for item in report.baselines if item["name"] == "application_log")
    assert complete["arc"] >= 0.95
    assert complete["tamper_detection_rate"] == 1.0
    assert complete["tamper_detection_rate"] > logs["tamper_detection_rate"]
    assert report.capture_overhead["latency_ms_plane"] > 0
    assert report.capture_overhead["latency_ms_baseline"] > 0
    assert report.capture_overhead["storage_bytes_plane"] > report.capture_overhead["storage_bytes_log"]
    assert report.reviewer_task["success"] == 1.0
    assert set(report.reviewer_task["identified"]) >= {
        "source",
        "model",
        "evidence",
        "guardrail",
        "human_action",
    }
    pipeline.close()
