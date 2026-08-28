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
