import json

from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.research import research_export
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def test_research_export_excludes_identifiers_and_payloads(tmp_path):
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
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    export = research_export(result)
    blob = str(export)
    assert export["export_type"] == "research"
    assert export["event_inclusion"]["clinical_events"] is True
    assert export["event_inclusion"]["access_events"] is False
    assert "Access, verification, and administrative events" in export["notice"]
    assert export["transaction_id"].startswith("tx_")
    assert export["subject_ref"].startswith("subj_")
    assert result.transaction.transaction_id not in blob
    assert "TEST-00001" not in blob
    assert "payload_ref" not in blob
    assert "bytes" not in blob
    assert export["events"]
    assert export["integrity"]["key_id"]
    assert export["model"]["prompt_version"]
    pipeline.close()


def test_research_export_scrubs_uuid_resource_ids(tmp_path):
    uuid = "f494111c-1660-e72f-a698-e9d6c2cf6424"
    fixture = tmp_path / "uuid-patient.json"
    fixture.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "timestamp": "2026-01-01T00:00:00Z",
                "entry": [
                    {"resource": {"resourceType": "Patient", "id": uuid}},
                    {
                        "resource": {
                            "resourceType": "Encounter",
                            "id": "enc-uuid",
                            "status": "finished",
                            "class": {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                "code": "AMB",
                            },
                            "subject": {"reference": f"Patient/{uuid}"},
                        }
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        ),
        fixture_path=fixture,
    )
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    export = research_export(result)
    blob = str(export)
    assert uuid not in blob
    assert f"Patient/{uuid}" not in blob
    pipeline.close()


def test_research_export_scrubs_arbitrary_ids_names_phones_and_dates(tmp_path):
    fixture = tmp_path / "named-patient.json"
    fixture.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "timestamp": "2026-01-01T00:00:00Z",
                "entry": [
                    {"resource": {"resourceType": "Patient", "id": "john-smith"}},
                    {
                        "resource": {
                            "resourceType": "Encounter",
                            "id": "enc-john-smith",
                            "status": "finished",
                            "class": {
                                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                "code": "AMB",
                            },
                            "subject": {"reference": "Patient/john-smith"},
                        }
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        ),
        fixture_path=fixture,
    )
    result = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
        comment="Call 555-123-4567 about John Smith DOB 1980-05-01",
    )
    export = research_export(result)
    blob = str(export)
    assert "john-smith" not in blob
    assert "John Smith" not in blob
    assert "555-123-4567" not in blob
    assert "1980-05-01" not in blob
    pipeline.close()
