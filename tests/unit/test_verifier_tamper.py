from datetime import UTC, datetime

from curie_audit_plane.integrity.chain import link_chain
from curie_audit_plane.integrity.hashing import hash_event
from curie_audit_plane.integrity.merkle import merkle_proof, merkle_root
from curie_audit_plane.integrity.signing import generate_keypair, sign_hex
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import EventType, VerificationStatus
from curie_audit_plane.models.manifests import IntegrityBatch
from tests.helpers import make_event


def _chained_events():
    types = [
        EventType.TRANSACTION_STARTED,
        EventType.INPUT_MANIFEST_CREATED,
        EventType.TRANSFORMATION_APPLIED,
        EventType.CONTEXT_MANIFEST_CREATED,
        EventType.MODEL_REQUESTED,
        EventType.MODEL_RESPONDED,
        EventType.STRUCTURED_OUTPUT_VALIDATED,
        EventType.GUARDRAIL_COMPLETED,
        EventType.HUMAN_ACTION_RECORDED,
        EventType.TRANSACTION_COMPLETED,
        EventType.INTEGRITY_PROOF_COMMITTED,
    ]
    raw = [
        make_event(event_id=f"evt-{index}", sequence_number=index, event_type=event_type)
        for index, event_type in enumerate(types)
    ]
    return link_chain(raw)


def _signed_batch(events, private_key: bytes, key_id: str = "test-key"):
    completed = next(event for event in events if event.event_type == EventType.TRANSACTION_COMPLETED)
    root = completed.event_hash
    merkle = merkle_root([root])
    proof = merkle_proof([root], 0)
    return IntegrityBatch(
        batch_id="batch-1",
        transaction_ids=[events[0].transaction_id],
        transaction_roots=[root],
        merkle_root=merkle,
        signature=sign_hex(merkle, private_key),
        key_id=key_id,
        signed_at=datetime.now(UTC),
        inclusion_index=0,
        inclusion_proof=proof.path,
    )


def test_clean_transaction_verifies():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.VERIFIED
    assert report.chain_ok is True
    assert report.merkle_ok is True
    assert report.signature_ok is True
    assert report.missing_events == []


def test_mutated_metadata_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    events[4] = events[4].model_copy(update={"payload_metadata": {"model_version": "mutated"}})
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.TAMPERED
    assert report.hash_failures


def test_deleted_event_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    deleted = events[:7] + events[8:]
    report = verify_transaction(deleted, batch, public_key)
    assert report.status in {VerificationStatus.TAMPERED, VerificationStatus.INCOMPLETE}


def test_reordered_events_are_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    events[2], events[3] = events[3], events[2]
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.TAMPERED


def test_broken_previous_hash_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    events[3] = events[3].model_copy(update={"previous_event_hash": "ab" * 32})
    events[3] = events[3].model_copy(
        update={"event_hash": hash_event(events[3].model_dump(mode="json"))}
    )
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.TAMPERED


def test_invalid_merkle_proof_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    batch = batch.model_copy(update={"inclusion_proof": ["ff" * 32]})
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.TAMPERED
    assert report.merkle_ok is False


def test_wrong_signature_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    _, other_public = generate_keypair()
    batch = _signed_batch(events, private_key)
    report = verify_transaction(events, batch, other_public)
    assert report.status == VerificationStatus.TAMPERED
    assert report.signature_ok is False


def test_missing_required_event_is_incomplete_when_chain_intact():
    types = [
        EventType.TRANSACTION_STARTED,
        EventType.INPUT_MANIFEST_CREATED,
        EventType.TRANSFORMATION_APPLIED,
        EventType.CONTEXT_MANIFEST_CREATED,
        EventType.MODEL_REQUESTED,
        EventType.MODEL_RESPONDED,
        EventType.STRUCTURED_OUTPUT_VALIDATED,
        EventType.GUARDRAIL_COMPLETED,
        EventType.TRANSACTION_COMPLETED,
    ]
    events = link_chain(
        [
            make_event(event_id=f"evt-{index}", sequence_number=index, event_type=event_type)
            for index, event_type in enumerate(types)
        ]
    )
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.INCOMPLETE
    assert EventType.HUMAN_ACTION_RECORDED.value in report.missing_events
    assert EventType.INTEGRITY_PROOF_COMMITTED.value in report.missing_events


def test_altered_key_id_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key, key_id="test-key")
    report = verify_transaction(events, batch, public_key, expected_key_id="other-key")
    assert report.status == VerificationStatus.TAMPERED
    assert report.signature_ok is False


def test_altered_transaction_id_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    batch = batch.model_copy(update={"transaction_ids": ["other-tx"]})
    report = verify_transaction(events, batch, public_key, transaction_id=events[0].transaction_id)
    assert report.status == VerificationStatus.TAMPERED
    assert report.merkle_ok is False


def test_altered_inclusion_index_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    batch = batch.model_copy(update={"inclusion_index": 3})
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.TAMPERED


def test_altered_transaction_root_is_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    batch = batch.model_copy(update={"transaction_roots": ["ab" * 32]})
    report = verify_transaction(events, batch, public_key)
    assert report.status == VerificationStatus.TAMPERED


def test_events_appended_after_seal_are_tampered():
    events = _chained_events()
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    extra = make_event(
        event_id="after-seal",
        sequence_number=len(events),
        event_type=EventType.UI_ACCESS_RECORDED,
        previous_event_hash=events[-1].event_hash,
    )
    extra = extra.model_copy(update={"event_hash": hash_event(extra.model_dump(mode="json"))})
    report = verify_transaction(events + [extra], batch, public_key)
    assert report.status == VerificationStatus.TAMPERED
    assert "seal" in report.reason


def test_missing_protected_content_is_incomplete(tmp_path):
    from curie_audit_plane.store.content import ProtectedContentStore

    events = _chained_events()
    store = ProtectedContentStore(tmp_path / "protected")
    payload = b'{"ok":true}'
    ref = store.put(payload, "application/json")
    digest = store.digest_of(payload)
    events[3] = events[3].model_copy(update={"payload_ref": ref, "payload_digest": digest})
    events[3] = events[3].model_copy(update={"event_hash": hash_event(events[3].model_dump(mode="json"))})
    from curie_audit_plane.integrity.chain import link_chain

    events = link_chain(
        [event.model_copy(update={"event_hash": "", "previous_event_hash": ""}) for event in events]
    )
    private_key, public_key = generate_keypair()
    batch = _signed_batch(events, private_key)
    (tmp_path / "protected" / ref.removeprefix("sha256:")).unlink()
    report = verify_transaction(events, batch, public_key, content_store=store)
    assert report.status == VerificationStatus.INCOMPLETE
    assert report.content_ok is False
    assert "content" in report.reason.lower() or "missing" in report.reason.lower()
