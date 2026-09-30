import json
from uuid import uuid4

from curie_audit_plane.evaluation.report import _evidence_coverage
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import EventType, HumanActionStatus
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
            key_id="opaque-key",
        )
    )


def _bundle(*, patient_id: str, resources: list[dict[str, object]]) -> dict[str, object]:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": "2026-01-01T00:00:00Z",
        "entry": [{"resource": resource} for resource in resources],
    }


def test_immutable_metadata_uses_opaque_tokens_for_arbitrary_ids(tmp_path):
    patient_id = "alt-99"
    resource_id = "enc-alt"
    fixture = tmp_path / "other-patient.json"
    fixture.write_text(
        json.dumps(
            _bundle(
                patient_id=patient_id,
                resources=[
                    {"resourceType": "Patient", "id": patient_id},
                    {
                        "resourceType": "Encounter",
                        "id": resource_id,
                        "status": "finished",
                        "class": {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": "AMB",
                        },
                        "subject": {"reference": f"Patient/{patient_id}"},
                    },
                ],
            )
        ),
        encoding="utf-8",
    )
    pipeline = _pipeline(tmp_path)
    pipeline.fixture_path = fixture
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    expected_subject = opaque_identifier(f"Patient/{patient_id}")
    expected_resource = opaque_identifier(resource_id)
    assert result.transaction.subject_ref == expected_subject
    started = next(event for event in result.events if event.event_type == EventType.TRANSACTION_STARTED)
    manifest = next(event for event in result.events if event.event_type == EventType.INPUT_MANIFEST_CREATED)
    immutable = json.dumps([event.model_dump(mode="json") for event in result.events])
    assert started.payload_metadata["subject_ref"] == expected_subject
    assert expected_resource in manifest.payload_metadata["resource_ids"]
    assert patient_id not in immutable
    assert resource_id not in immutable
    identity = json.loads(pipeline.services.content.get(started.payload_metadata["identity_ref"]))
    assert identity["subject_raw"] == f"Patient/{patient_id}"
    assert identity["subject_opaque"] == expected_subject
    pipeline.close()


def test_opaque_tokens_cover_uuids_and_custom_resource_types(tmp_path):
    patient_id = str(uuid4())
    custom_id = f"widget-{uuid4()}"
    fixture = tmp_path / "custom.json"
    fixture.write_text(
        json.dumps(
            _bundle(
                patient_id=patient_id,
                resources=[
                    {"resourceType": "Patient", "id": patient_id},
                    {"resourceType": "CustomWidget", "id": custom_id},
                ],
            )
        ),
        encoding="utf-8",
    )
    pipeline = _pipeline(tmp_path)
    pipeline.fixture_path = fixture
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    immutable = json.dumps([event.model_dump(mode="json") for event in result.events])
    assert result.transaction.subject_ref == opaque_identifier(f"Patient/{patient_id}")
    assert patient_id not in immutable
    assert custom_id not in immutable
    assert opaque_identifier(custom_id) in json.dumps(result.events[1].payload_metadata)
    pipeline.close()


def test_evidence_coverage_resolves_raw_ids_via_identity_map(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    coverage = _evidence_coverage(result, pipeline.services.content)
    assert coverage.value == 1.0
    pipeline.close()
