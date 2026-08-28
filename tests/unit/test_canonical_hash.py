from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import hash_event, sha256_hex


def test_canonicalize_sorts_keys_and_drops_whitespace():
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonicalize_is_stable_for_nested_objects():
    left = {"outer": {"z": True, "m": [2, 1]}, "id": "t1"}
    right = {"id": "t1", "outer": {"m": [2, 1], "z": True}}
    assert canonicalize(left) == canonicalize(right)


def test_hash_event_omits_event_hash_field():
    event = {"event_id": "e1", "event_hash": "deadbeef", "n": 1}
    expected = sha256_hex(canonicalize({"event_id": "e1", "n": 1}))
    assert hash_event(event) == expected
    assert hash_event(event) == hash_event({"event_id": "e1", "n": 1})


def test_independent_sha256_of_canonical_bytes():
    payload = canonicalize({"schema_version": "1.0.0", "event_id": "e1"})
    import hashlib

    assert sha256_hex(payload) == hashlib.sha256(payload).hexdigest()
