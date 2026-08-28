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

    encoded = report.to_json_dict()
    metrics = {metric["name"]: metric for metric in encoded["metrics"]}
    tamper_cases = [case for case in encoded["cases"] if case.get("kind") == "tamper"]
    csv_tamper = next(row for row in report.to_csv_rows() if row["name"] == "tamper_detection_rate")
    assert metrics["field_presence_arc"]["value"] >= 0.95
    assert metrics["independently_verified_arc"]["value"] >= 0.95
    assert metrics["independently_verified_arc"]["denominator"] == 20
    assert "persisted" in metrics["independently_verified_arc"]["notes"].lower()
    assert "repository" in metrics["independently_verified_arc"]["notes"].lower()
    assert metrics["audit_reconstruction_completeness"]["value"] == metrics["independently_verified_arc"]["value"]
    assert metrics["tamper_detection_rate"]["value"] == 1.0
    assert metrics["tamper_detection_rate"]["denominator"] == len(tamper_cases)
    assert metrics["tamper_detection_rate"]["denominator"] == 19
    assert csv_tamper["denominator"] == metrics["tamper_detection_rate"]["denominator"]
    assert csv_tamper["numerator"] == metrics["tamper_detection_rate"]["numerator"]
    assert csv_tamper["value"] == metrics["tamper_detection_rate"]["value"]
    assert metrics["false_tamper_rate"]["value"] == 0.0
    assert metrics["replay_fidelity"]["status"] == "MEASURED"
    assert metrics["evidence_attribution_coverage"]["value"] == 1.0
    assert metrics["human_action_capture_completeness"]["value"] == 1.0
    assert metrics["human_action_capture_completeness"]["denominator"] == 1
    assert metrics["reviewer_task_success"]["status"] == "SCRIPTED_PROXY"
    assert metrics["capture_overhead"]["status"] == "MEASURED"
    assert "allocated" in metrics["storage_overhead"]["notes"].lower()
    assert metrics["storage_total_allocated"]["unit"] == "allocated_multiplier"
    assert metrics["storage_overhead_logical"]["status"] == "MEASURED"
    assert metrics["verification_latency"]["status"] == "MEASURED"
    assert encoded["schema_version"] == "curie-evaluation.v1.1"
    assert encoded["runtime"] == "deterministic-stub"
    experiment = encoded["experiment"]
    assert experiment["fixture_alias"] == "synthetic-encounter-bundle"
    assert experiment["command"].startswith("curie-audit-plane evaluate")
    assert experiment["python_version"]
    assert "generated_at" in experiment
    assert experiment["provider"] != "configured"
    assert experiment["model_id"]
    assert experiment["prompt_version"]
    assert experiment["decoding_params"] is not None
    assert experiment["endpoint_class"]
    assert "git_dirty" in experiment
    assert experiment["synthea_pinned"] is False
    assert experiment["synthea_version"] == "NOT_PINNED"
    assert {row["independence"] for row in encoded["baselines"]} >= {
        "unrecorded_workflow",
        "source_bundle",
        "audit_chain",
    }
    assert encoded["ablations"]
    assert {row["name"] for row in encoded["ablations"]} >= {
        "full",
        "omit_input_manifests",
        "omit_transformations",
        "omit_model_metadata",
        "omit_evidence",
        "omit_proofs",
        "omit_human_provenance",
    }
    access_names = {row["name"] for row in encoded["access_control"]["cases"]}
    assert access_names >= {
        "reviewer_read",
        "investigator_verify",
        "admin_content",
        "denied_unauthenticated",
        "reviewer_denied_export",
        "investigator_denied_output",
        "investigator_denied_content",
        "reviewer_output",
        "investigator_export",
        "missing_transaction",
        "global_scope_list",
    }
    assert encoded["access_control"]["pass_rate"]["interval"] == "wilson"
    access_blob = json.dumps(encoded["access_control"])
    assert "eval-admin-token" not in access_blob
    assert "Bearer " not in access_blob
    assert {case["role"] for case in encoded["access_control"]["cases"]} <= {
        "admin",
        "reviewer",
        "investigator",
        "unauthenticated",
    }
    pipeline.close()


def test_evaluation_report_serializes_stable_json_and_csv_rows(tmp_path):
    pipeline = _pipeline(tmp_path)
    report = build_evaluation_report(pipeline)
    REQUIRED = {
        "accept", "modify", "reject", "guardrail_warn", "guardrail_block",
        "synthea_sliced", "two_step_accept", "block_override_accept",
        "natural_guardrail_warn", "natural_guardrail_block", "provider_failure",
        "sparse_encounter", "synthea_sliced_second", "modify_evidence",
        "replay_substitution", "access_audit",
    }

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
    assert {row["name"] for row in rows if row["row_type"] == "scenario"} >= REQUIRED
    assert {row["row_type"] for row in rows} >= {
        "metric",
        "case",
        "scenario",
        "ablation",
        "access",
    }
    assert {row["result"] for row in rows if row["row_type"] == "access"} <= {
        "admin",
        "reviewer",
        "investigator",
        "unauthenticated",
        "",
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
