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
    hash_only = next(item for item in report.baselines if item["name"] == "hash_only")
    fhir = next(item for item in report.baselines if item["name"] == "fhir_projection")
    assert complete["implementation"] == "complete_audit_plane"
    assert logs["implementation"] == "application_jsonl"
    assert hash_only["implementation"] == "hash_only_jsonl"
    assert fhir["implementation"] == "fhir_r4_projection"
    assert complete["arc"] >= 0.95
    assert complete["arc"] > logs["arc"]
    assert complete["arc"] > fhir["arc"]
    assert complete["tamper_detection_rate"] == 1.0
    assert complete["tamper_detection_rate"] > logs["tamper_detection_rate"]
    assert hash_only["tamper_detection_rate"] >= logs["tamper_detection_rate"]
    overhead = report.capture_overhead
    assert overhead["n"] >= 3
    assert overhead["warmup"] >= 1
    assert overhead["latency_ms_plane_mean"] > 0
    assert overhead["latency_ms_baseline_mean"] > 0
    assert "ci95_low" in overhead["latency_ratio"]
    assert overhead["storage_bytes_audit_mean"] > 0
    assert overhead["storage_bytes_content_mean"] > 0
    assert overhead["storage_bytes_log_mean"] > 0
    assert "latency_ratio = (T_plane - T_no_audit_workflow) / T_no_audit_workflow" in overhead["formulas"]
    assert overhead["baseline_name"] == "no_audit_workflow"
    assert overhead["latency_ratio"]["method"] == "paired-normal"
    assert "storage_ratio = (bytes_plane - bytes_no_audit_workflow) / bytes_no_audit_workflow" in overhead["formulas"]
    assert report.reviewer_task["success"] == 1.0
    assert set(report.reviewer_task["identified"]) >= {
        "source",
        "model",
        "evidence",
        "guardrail",
        "human_action",
    }
    pipeline.close()
