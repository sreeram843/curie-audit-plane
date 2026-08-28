from curie_audit_plane.models.enums import EventType
from curie_audit_plane.stages import EVENT_STAGES, stage_for
from curie_audit_plane.views import STAGE_FLOW


def test_every_event_type_has_a_stage_and_sankey_ids_match():
    for event_type in EventType:
        assert event_type.value in EVENT_STAGES
        assert stage_for(event_type.value)
    for node_id in STAGE_FLOW:
        assert node_id in EVENT_STAGES.values()
    assert stage_for("input.manifest.created") == "fhir_inputs"
    assert stage_for("human.action_recorded") == "human_action"
    assert stage_for("integrity.proof_committed") == "integrity_proof"
