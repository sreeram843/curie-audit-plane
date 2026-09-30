import json

import pytest
from pydantic import ValidationError

from curie_audit_plane.adapters.completion import CompletionRequest
from curie_audit_plane.evaluation.encounter_slice import slice_first_encounter
from curie_audit_plane.evaluation.scenarios import (
    _WARN_OUTPUT,
    _with_output,
    discover_synthea_bundles,
    run_scenario_matrix,
    synthea_manifest,
)
from curie_audit_plane.fhir.loader import iter_resources
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import (
    GuardrailStatus,
    HumanActionStatus,
    TransactionStatus,
    VerificationStatus,
)
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.privacy import opaque_identifier
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
            key_id="scenario-key",
        )
    )


def test_slice_first_encounter_keeps_allowed_types_only():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": "2026-01-02T00:00:00Z",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p-1"}},
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e-1",
                    "subject": {"reference": "Patient/p-1"},
                }
            },
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "e-2",
                    "subject": {"reference": "Patient/p-1"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o-1",
                    "subject": {"reference": "Patient/p-1"},
                    "encounter": {"reference": "Encounter/e-1"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "o-2",
                    "subject": {"reference": "Patient/p-1"},
                    "encounter": {"reference": "Encounter/e-2"},
                }
            },
            {"resource": {"resourceType": "Claim", "id": "c-1"}},
        ],
    }

    sliced = slice_first_encounter(bundle)
    types = {item["resourceType"] for item in iter_resources(sliced)}
    ids = {item["id"] for item in iter_resources(sliced)}
    assert types <= {"Patient", "Encounter", "Condition", "MedicationRequest", "Observation", "DiagnosticReport"}
    assert ids == {"p-1", "e-1", "o-1"}
    assert "o-2" not in ids
    assert "c-1" not in ids


def test_slice_first_encounter_matches_urn_uuid_references():
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "id": "p-uuid"}},
            {
                "resource": {
                    "resourceType": "Encounter",
                    "id": "enc-uuid",
                    "subject": {"reference": "urn:uuid:p-uuid"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-keep",
                    "subject": {"reference": "urn:uuid:p-uuid"},
                    "encounter": {"reference": "urn:uuid:enc-uuid"},
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "id": "obs-drop",
                    "subject": {"reference": "urn:uuid:p-uuid"},
                    "encounter": {"reference": "urn:uuid:other-enc"},
                }
            },
        ],
    }

    sliced = slice_first_encounter(bundle)
    ids = {item["id"] for item in iter_resources(sliced)}
    assert ids == {"p-uuid", "enc-uuid", "obs-keep"}


def test_scenario_matrix_covers_workflow_arms(tmp_path):
    pipeline = _pipeline(tmp_path)
    report = run_scenario_matrix(pipeline)
    REQUIRED = {
        "accept", "modify", "reject", "guardrail_warn", "guardrail_block",
        "synthea_sliced", "two_step_accept", "block_override_accept",
        "natural_guardrail_warn", "natural_guardrail_block", "provider_failure",
        "sparse_encounter", "synthea_sliced_second", "modify_evidence",
        "replay_substitution", "access_audit",
    }
    assert {item["name"] for item in report["scenarios"]} >= REQUIRED
    by_name = {item["name"]: item for item in report["scenarios"]}
    assert by_name["accept"]["transaction_status"] == TransactionStatus.COMPLETED.value
    assert by_name["accept"]["human_action"] == HumanActionStatus.ACCEPT.value
    assert by_name["modify"]["human_action"] == HumanActionStatus.MODIFY.value
    assert by_name["reject"]["human_action"] == HumanActionStatus.REJECT.value
    assert by_name["guardrail_warn"]["forced_guardrail"] == GuardrailStatus.WARN.value
    assert by_name["guardrail_block"]["transaction_status"] == TransactionStatus.BLOCKED.value
    assert by_name["accept"]["arc"] == 1.0
    assert by_name["two_step_accept"]["transaction_status"] == TransactionStatus.COMPLETED.value
    assert by_name["two_step_accept"]["waiting_status"] == TransactionStatus.WAITING_FOR_REVIEW.value
    assert by_name["block_override_accept"]["transaction_status"] == TransactionStatus.COMPLETED.value
    assert by_name["block_override_accept"]["human_action"] == HumanActionStatus.ACCEPT.value
    assert by_name["block_override_accept"]["override_policy_version"] == "override.v1"
    assert by_name["natural_guardrail_warn"]["transaction_status"] == TransactionStatus.COMPLETED.value
    assert by_name["natural_guardrail_warn"]["verification_status"] == VerificationStatus.VERIFIED.value
    assert by_name["accept"]["guardrail_results"]["uncertainty.v1"] == GuardrailStatus.PASS.value
    assert by_name["natural_guardrail_warn"]["guardrail_results"]["evidence_refs.v1"] == GuardrailStatus.PASS.value
    assert by_name["natural_guardrail_warn"]["guardrail_results"]["phi_scan.v1"] == GuardrailStatus.WARN.value
    assert by_name["natural_guardrail_warn"]["guardrail_results"]["uncertainty.v1"] == GuardrailStatus.PASS.value
    assert by_name["natural_guardrail_warn"]["arc"] == 1.0
    assert by_name["natural_guardrail_block"]["transaction_status"] == TransactionStatus.BLOCKED.value
    assert by_name["natural_guardrail_block"]["guardrail_results"]["evidence_refs.v1"] == GuardrailStatus.BLOCK.value
    assert by_name["natural_guardrail_block"]["arc"] < 1.0
    assert by_name["provider_failure"]["transaction_status"] == TransactionStatus.FAILED.value
    assert by_name["sparse_encounter"]["transaction_status"] == TransactionStatus.COMPLETED.value
    assert by_name["sparse_encounter"]["subject_ref"].startswith("tok_")
    assert by_name["modify_evidence"]["human_action"] == HumanActionStatus.MODIFY.value
    assert (
        by_name["modify_evidence"]["source_output_digest"]
        != by_name["modify_evidence"]["final_output_digest"]
    )
    assert (
        by_name["modify_evidence"]["source_evidence_references"]
        != by_name["modify_evidence"]["final_evidence_references"]
    )
    assert by_name["replay_substitution"]["replay_result"] == "DIVERGENT"
    assert by_name["replay_substitution"]["verification_status"] == VerificationStatus.VERIFIED.value
    assert by_name["access_audit"]["access_event_count"] >= 2
    assert by_name["access_audit"]["verification_status"] == VerificationStatus.VERIFIED.value
    synthea_second = by_name["synthea_sliced_second"]
    synthea_second_status = synthea_second.get("status", synthea_second.get("transaction_status"))
    assert synthea_second_status is not None
    if synthea_second_status != "NOT_AVAILABLE":
        assert (
            synthea_second["subject_ref"]
            != by_name["synthea_sliced"]["subject_ref"]
        )
    pipeline.close()


def test_with_output_injects_warn_payload_without_calling_inner():
    def boom(_request):
        raise AssertionError("wrapped completer must not call the inner provider")

    wrapped = _with_output(boom, _WARN_OUTPUT)
    result = wrapped(
        CompletionRequest(
            context_digest="abc123",
            context=object(),
            evidence_ids=["obs-bp-TEST-00001"],
            prompt_version="clinical-summary.v1",
        )
    )
    assert "TEST-00001" in result.output.summary
    assert result.output.evidence_references == ["obs-bp-TEST-00001"]
    assert result.output.uncertainty


def test_discover_synthea_bundles_rejects_path_outside_approved_root(tmp_path, monkeypatch):
    fake = tmp_path / "hospital-patient.json"
    fake.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "hospital-mrn-99",
                            "identifier": [
                                {
                                    "system": "https://github.com/synthetichealth/synthea",
                                    "value": "hospital-mrn-99",
                                }
                            ],
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("CURIE_SYNTHEA_BUNDLE", str(fake))
    monkeypatch.setattr(
        "curie_audit_plane.evaluation.scenarios.approved_synthea_roots",
        lambda: [tmp_path / "approved-empty"],
    )
    assert discover_synthea_bundles() == []


def test_discover_synthea_bundles_accepts_marked_file_under_approved_root(tmp_path, monkeypatch):
    approved = tmp_path / "approved"
    approved.mkdir()
    bundle = approved / "synthea-patient.json"
    bundle.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [
                    {
                        "resource": {
                            "resourceType": "Patient",
                            "id": "syn-1",
                            "identifier": [
                                {
                                    "system": "https://github.com/synthetichealth/synthea",
                                    "value": "syn-1",
                                }
                            ],
                        }
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("CURIE_SYNTHEA_BUNDLE", raising=False)
    monkeypatch.delenv("CURIE_SYNTHEA_DIR", raising=False)
    monkeypatch.setattr(
        "curie_audit_plane.evaluation.scenarios.approved_synthea_roots",
        lambda: [approved],
    )
    assert discover_synthea_bundles() == [bundle]
    record = synthea_manifest()
    assert record["license"]
    assert record["source"]
    assert record["pinned"] is False
    assert record["generator_version"] is None


def test_synthea_manifest_rejects_invalid_schema(tmp_path, monkeypatch):
    bad = tmp_path / "approved-manifest.json"
    bad.write_text('{"schema_version": "curie-synthea-manifest.v1"}', encoding="utf-8")
    monkeypatch.setattr(
        "curie_audit_plane.evaluation.scenarios._SYNTHEA_MANIFEST_PATH",
        bad,
    )
    with pytest.raises(ValidationError):
        synthea_manifest()


def test_pipeline_subject_ref_is_opaque_token_for_patient_resource(tmp_path):
    fixture = tmp_path / "other-patient.json"
    fixture.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "timestamp": "2026-01-01T00:00:00Z",
                "entry": [
                    {"resource": {"resourceType": "Patient", "id": "alt-99"}},
                    {
                        "resource": {
                            "resourceType": "Encounter",
                            "id": "enc-alt",
                            "status": "finished",
                            "class": {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                "code": "AMB",
                            },
                            "subject": {"reference": "Patient/alt-99"},
                        }
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    pipeline = _pipeline(tmp_path)
    pipeline.fixture_path = fixture
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    assert result.transaction.subject_ref == opaque_identifier("Patient/alt-99")
    assert "alt-99" not in json.dumps([event.model_dump(mode="json") for event in result.events])
    pipeline.close()
