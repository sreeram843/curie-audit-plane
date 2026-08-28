import hashlib
from collections.abc import Mapping

from curie_audit_plane.integrity.canonical import canonicalize

EVENT_HASH_FIELD = "event_hash"
GENESIS_HASH = "0" * 64


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_event(event: Mapping[str, object]) -> str:
    body = {key: value for key, value in event.items() if key != EVENT_HASH_FIELD}
    return sha256_hex(canonicalize(body))
