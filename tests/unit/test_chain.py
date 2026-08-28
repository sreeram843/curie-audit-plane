from curie_audit_plane.integrity.chain import link_chain, verify_chain
from curie_audit_plane.integrity.hashing import GENESIS_HASH
from tests.helpers import make_event


def test_first_event_links_to_genesis():
    events = link_chain([make_event(sequence_number=0), make_event(event_id="evt-2", sequence_number=1)])
    assert events[0].previous_event_hash == GENESIS_HASH
    assert events[1].previous_event_hash == events[0].event_hash
    assert events[0].event_hash
    assert events[1].event_hash != events[0].event_hash


def test_reordering_breaks_chain_verification():
    chained = link_chain(
        [
            make_event(sequence_number=0),
            make_event(event_id="evt-2", sequence_number=1),
            make_event(event_id="evt-3", sequence_number=2),
        ]
    )
    reordered = [chained[0], chained[2], chained[1]]
    report = verify_chain(reordered)
    assert report.ok is False
    assert "order" in report.reason.lower() or "sequence" in report.reason.lower()


def test_mutation_breaks_event_hash():
    chained = link_chain([make_event(sequence_number=0)])
    mutated = chained[0].model_copy(
        update={"payload_metadata": {"purpose": "tampered", "model_version": "evil"}}
    )
    report = verify_chain([mutated])
    assert report.ok is False


def test_payload_tamper_with_intact_neighbor_links_is_tampered():
    from curie_audit_plane.integrity.chain import per_event_hash_statuses

    chained = link_chain(
        [
            make_event(sequence_number=0),
            make_event(event_id="evt-2", sequence_number=1),
            make_event(event_id="evt-3", sequence_number=2),
        ]
    )
    tampered = chained[1].model_copy(update={"payload_metadata": {"purpose": "altered-without-rehash"}})
    events = [chained[0], tampered, chained[2]]
    assert events[1].previous_event_hash == events[0].event_hash
    assert events[2].previous_event_hash == chained[1].event_hash
    statuses = per_event_hash_statuses(events)
    assert statuses[tampered.event_id] == "TAMPERED"
    assert statuses[chained[0].event_id] == "VERIFIED"
