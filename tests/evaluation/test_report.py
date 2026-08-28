import json

from curie_audit_plane.evaluation.report import build_evaluation_report
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def _pipeline(tmp_path):
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


def test_evaluation_report_contains_numeric_metrics_and_explicit_study_gaps(tmp_path):
    pipeline = _pipeline(tmp_path)
    report = build_evaluation_report(pipeline)

    metrics = {metric["name"]: metric for metric in report.to_json_dict()["metrics"]}
    assert metrics["audit_reconstruction_completeness"]["value"] >= 0.95
    assert metrics["audit_reconstruction_completeness"]["denominator"] == 20
    assert metrics["tamper_detection_rate"]["value"] == 1.0
    assert metrics["false_tamper_rate"]["value"] == 0.0
    assert metrics["replay_fidelity"]["status"] == "MEASURED"
    assert metrics["evidence_attribution_coverage"]["value"] == 1.0
    assert metrics["human_action_capture_completeness"]["value"] == 1.0
    assert metrics["human_action_capture_completeness"]["denominator"] == 1
    assert metrics["reviewer_task_success"]["status"] == "SCRIPTED_PROXY"
    assert metrics["capture_overhead"]["status"] == "MEASURED"
    assert metrics["verification_latency"]["status"] == "MEASURED"
    assert report.to_json_dict()["schema_version"] == "curie-evaluation.v1"
    assert report.to_json_dict()["runtime"] == "deterministic-stub"
    pipeline.close()


def test_evaluation_report_serializes_stable_json_and_csv_rows(tmp_path):
    pipeline = _pipeline(tmp_path)
    report = build_evaluation_report(pipeline)

    encoded = json.dumps(report.to_json_dict())
    assert "bounded_context" not in encoded
    assert "private_key" not in encoded
    rows = report.to_csv_rows()
    assert rows
    assert rows[0]["row_type"] == "metric"
    assert {row["name"] for row in rows if row["row_type"] == "case"} >= {
        "clean",
        "replay_stub",
    }
    assert list(rows[0]) == [
        "row_type",
        "name",
        "kind",
        "status",
        "value",
        "numerator",
        "denominator",
        "unit",
        "notes",
        "detected",
        "result",
    ]
    pipeline.close()
