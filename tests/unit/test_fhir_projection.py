from curie_audit_plane.fhir.projection import project_audit_events, project_provenance
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def test_provenance_and_audit_event_projections_have_required_r4_fields(tmp_path):
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
    provenance = project_provenance(result)
    assert provenance["resourceType"] == "Provenance"
    assert provenance["target"]
    assert provenance["recorded"]
    assert {agent["who"]["display"] for agent in provenance["agent"]} >= {
        "curie-audit-plane",
        "reviewer@curie.local",
    }
    assert any(entity["what"]["reference"].startswith("Patient/") for entity in provenance["entity"])
    assert any(entity["what"]["reference"].startswith("Encounter/") for entity in provenance["entity"])
    assert any(entity["what"]["reference"].startswith("Observation/") for entity in provenance["entity"])
    model_entity = next(entity for entity in provenance["entity"] if entity["role"]["text"] == "model-manifest")
    assert model_entity["what"]["identifier"]["value"]
    assert model_entity["what"]["identifier"]["system"] == "https://curie.local/model-manifest"

    audit_events = project_audit_events(result)
    types = {item["subtype"][0]["coding"][0]["code"] for item in audit_events}
    for required in (
        "transaction.started",
        "model.requested",
        "guardrail.completed",
        "human.action_recorded",
        "integrity.proof_committed",
    ):
        assert required in types
    for item in audit_events:
        assert item["resourceType"] == "AuditEvent"
        assert item["recorded"]
        assert item["agent"]
        assert item["subtype"][0]["coding"][0]["code"]
        assert item["subtype"][0]["coding"][0]["system"]
        assert item["subtype"][0]["coding"][0]["display"]
    pipeline.services.audit.close()
