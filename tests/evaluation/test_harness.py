import sqlite3

import pytest

from curie_audit_plane.evaluation.harness import _logical_sqlite_bytes, run_evaluation_harness
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore
from tests.helpers import make_event


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
    assert logs["independence"] == "unrecorded_workflow"
    assert hash_only["independence"] == "unrecorded_workflow"
    assert fhir["independence"] == "source_bundle"
    assert complete["independence"] == "audit_chain"
    assert complete["arc"] >= 0.95
    assert complete["arc"] > logs["arc"]
    assert complete["arc"] > fhir["arc"]
    assert complete["tamper_detection_rate"] == 1.0
    assert complete["tamper_detection_rate"] > logs["tamper_detection_rate"]
    assert hash_only["tamper_detection_rate"] >= logs["tamper_detection_rate"]
    overhead = report.capture_overhead
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
    assert overhead["n"] >= 30
    assert "storage_overhead_allocated = (bytes_allocated_plane - bytes_allocated_baseline) / bytes_allocated_baseline" in overhead["formulas"]
    assert "storage_total_allocated = bytes_allocated_plane / bytes_allocated_baseline" in overhead["formulas"]
    allocated_plane = overhead["storage_bytes_allocated_plane"]
    allocated_baseline = overhead["storage_bytes_allocated_baseline"]
    assert overhead["storage_overhead_allocated"] == pytest.approx(
        (allocated_plane - allocated_baseline) / allocated_baseline
    )
    assert overhead["storage_total_allocated"] == pytest.approx(allocated_plane / allocated_baseline)
    assert overhead["storage_bytes_logical_plane"] < allocated_plane
    assert overhead["storage_bytes_logical_baseline"] > 0
    assert overhead["storage_bytes_audit_allocated_mean"] >= overhead["storage_bytes_audit_logical_mean"]
    assert report.reviewer_task["success"] == 1.0
    assert set(report.reviewer_task["identified"]) >= {
        "source",
        "model",
        "evidence",
        "guardrail",
        "human_action",
    }
    pipeline.close()


def test_logical_sqlite_bytes_count_utf8_octets_not_characters(tmp_path):
    path = tmp_path / "audit.sqlite"
    store = AuditStore(path)
    store.create_transaction("tx-1", "purpose", "Patient/x")
    store.append_event(
        make_event(
            event_id="e0",
            transaction_id="tx-1",
            sequence_number=0,
            payload_metadata={"label": "μ"},
        )
    )
    store.close()

    conn = sqlite3.connect(path)
    event_json = conn.execute("SELECT event_json FROM events").fetchone()[0]
    row = conn.execute(
        "SELECT transaction_id, purpose, subject_ref, status, created_at, ended_at FROM transactions"
    ).fetchone()
    conn.close()

    utf8_bytes = len(event_json.encode("utf-8")) + sum(
        len((column or "").encode("utf-8")) for column in row
    )
    character_count = len(event_json) + sum(len(column or "") for column in row)
    assert "μ" in event_json
    assert utf8_bytes == character_count + 1
    assert _logical_sqlite_bytes(path) == utf8_bytes
