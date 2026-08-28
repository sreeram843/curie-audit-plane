from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore
from curie_audit_plane.views import CAPTION, sankey_view


def test_sankey_counts_recorded_artifacts_and_declares_noncausal_metric(tmp_path):
    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
        )
    )
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    view = sankey_view(result.events)
    assert view["metric"] == "artifact_count"
    assert view["caption"] == CAPTION
    assert "causal influence" in str(view["caption"]).lower()
    counts = {node["id"]: node["artifact_count"] for node in view["nodes"]}
    assert counts["fhir_inputs"] == 1
    assert counts["transformations"] == 3
    assert counts["guardrails"] >= 1
    assert counts["human_action"] == 1
    assert counts["integrity_proof"] == 1
    assert all(edge["metric"] == "artifact_count" for edge in view["edges"])
    by_id = {node["id"]: node for node in view["nodes"]}
    for node in view["nodes"]:
        assert len(node["event_ids"]) == node["artifact_count"]
    transform_ids = by_id["transformations"]["event_ids"]
    context_ids = by_id["context"]["event_ids"]
    edge = next(item for item in view["edges"] if item["source"] == "transformations" and item["target"] == "context")
    assert set(edge["event_ids"]) != set(transform_ids) | set(context_ids)
    assert set(edge["event_ids"]) <= set(transform_ids) | set(context_ids)
    assert len(edge["event_ids"]) == 2
    assert edge["event_ids"][-1] == context_ids[0]
    assert edge["event_ids"][0] == transform_ids[-1]
    assert all(item["event_ids"] for item in view["edges"] if item["value"])
    pipeline.services.audit.close()
