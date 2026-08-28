import pytest

from curie_audit_plane.models.event import AuditEventRecord
from curie_audit_plane.store.content import ProtectedContentStore
from tests.helpers import make_event


def test_put_returns_sha256_ref_and_get_roundtrips(tmp_path):
    store = ProtectedContentStore(tmp_path / "protected")
    ref = store.put(b'{"resourceType":"Patient"}', "application/fhir+json")
    assert ref.startswith("sha256:")
    assert store.get(ref) == b'{"resourceType":"Patient"}'


def test_malformed_ref_is_rejected(tmp_path):
    store = ProtectedContentStore(tmp_path / "protected")
    with pytest.raises(ValueError, match="malformed"):
        store.get("sha256:not-hex")
    with pytest.raises(ValueError, match="malformed"):
        store.get("../etc/passwd")


def test_digest_matches_payload_bytes(tmp_path):
    store = ProtectedContentStore(tmp_path / "protected")
    payload = b'{"resourceType":"Observation"}'
    ref = store.put(payload, "application/fhir+json")
    assert ref.removeprefix("sha256:") == store.digest_of(payload)


def test_audit_event_payload_metadata_rejects_clinical_keys():
    with pytest.raises(ValueError, match="clinical"):
        make_event(payload_metadata={"resource": {"resourceType": "Patient"}})


def test_audit_event_payload_metadata_rejects_hidden_reasoning():
    with pytest.raises(ValueError):
        AuditEventRecord.model_validate(
            make_event().model_dump(mode="json") | {"payload_metadata": {"chain_of_thought": "secret"}}
        )
