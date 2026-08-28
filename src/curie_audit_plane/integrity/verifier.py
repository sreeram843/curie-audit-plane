import json
from datetime import UTC, datetime
from typing import Any

from curie_audit_plane.integrity.chain import verify_chain
from curie_audit_plane.integrity.merkle import MerkleProof, verify_merkle_proof
from curie_audit_plane.integrity.signing import verify_signature
from curie_audit_plane.models.enums import REQUIRED_SUCCESS_EVENTS, EventType, VerificationStatus
from curie_audit_plane.models.event import AuditEventRecord
from curie_audit_plane.models.manifests import IntegrityBatch
from curie_audit_plane.models.report import VerificationReport


def _completed_leaf(events: list[AuditEventRecord]) -> str:
    completed = next(
        (
            event
            for event in events
            if event.event_type in {EventType.TRANSACTION_COMPLETED, EventType.TRANSACTION_FAILED}
        ),
        None,
    )
    if completed is not None:
        return completed.event_hash
    return events[-1].event_hash if events else ""


def _events_after_seal(events: list[AuditEventRecord]) -> bool:
    sealed = False
    for event in events:
        if event.event_type == EventType.INTEGRITY_PROOF_COMMITTED:
            sealed = True
            continue
        if sealed:
            return True
    return False


def _verify_content_refs(
    events: list[AuditEventRecord],
    content_store: Any,
) -> tuple[bool, str]:
    if content_store is None:
        return True, ""
    for event in events:
        ref = event.payload_ref
        if not ref:
            continue
        try:
            payload = content_store.get(ref)
        except FileNotFoundError:
            return False, f"protected content missing for {event.event_type.value}"
        except ValueError as exc:
            return False, str(exc)
        digest = event.payload_digest
        if digest and content_store.digest_of(payload) != digest:
            return False, f"protected content digest mismatch for {event.event_type.value}"
        if event.event_type == EventType.RETRIEVAL_COMPLETED:
            recorded = event.payload_metadata.get("corpus_version")
            try:
                body = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                body = None
            if recorded and isinstance(body, list):
                versions = {
                    item.get("corpus_version")
                    for item in body
                    if isinstance(item, dict) and item.get("corpus_version")
                }
                if versions and recorded not in versions:
                    return False, "corpus version mismatch for retrieval.completed"
    return True, ""


def verify_transaction(
    events: list[AuditEventRecord],
    batch: IntegrityBatch | None,
    public_key: bytes,
    *,
    expected_key_id: str | None = None,
    transaction_id: str | None = None,
    content_store: Any = None,
) -> VerificationReport:
    verified_at = datetime.now(UTC)
    scope = ["chain", "hashes", "required_events"]
    if content_store is not None:
        scope.append("content_refs")
    chain = verify_chain(events)
    present = {event.event_type for event in events}
    missing = [event_type.value for event_type in REQUIRED_SUCCESS_EVENTS if event_type not in present]
    stale = _events_after_seal(events)
    claimed_id = transaction_id or (events[0].transaction_id if events else "")

    merkle_ok = True
    signature_ok = True
    key_id = ""
    reason = ""
    if batch is not None:
        scope.extend(["merkle", "signature", "key_id", "inclusion"])
        key_id = batch.key_id
        leaf = _completed_leaf(events)
        if expected_key_id and batch.key_id != expected_key_id:
            signature_ok = False
            reason = "key_id mismatch"
        if claimed_id and claimed_id not in batch.transaction_ids:
            merkle_ok = False
            reason = reason or "transaction_id mismatch"
        if batch.inclusion_index is None or batch.inclusion_index < 0:
            merkle_ok = False
            reason = reason or "invalid inclusion_index"
        elif batch.inclusion_index >= len(batch.transaction_roots):
            merkle_ok = False
            reason = reason or "inclusion_index out of range"
        elif batch.transaction_roots[batch.inclusion_index] != leaf:
            merkle_ok = False
            reason = reason or "proof leaf does not match transaction root"
        proof = MerkleProof(index=batch.inclusion_index or 0, path=list(batch.inclusion_proof))
        if merkle_ok and not (bool(leaf) and verify_merkle_proof(leaf, proof, batch.merkle_root)):
            merkle_ok = False
            reason = reason or "invalid Merkle proof"
        if not verify_signature(batch.merkle_root, batch.signature, public_key):
            signature_ok = False
            reason = reason or "invalid signature"
        if stale:
            merkle_ok = False
            reason = reason or "events appended after seal"

    if stale and batch is None:
        merkle_ok = False
        reason = reason or "events appended after seal"

    if not chain.ok or not merkle_ok or not signature_ok:
        status = VerificationStatus.TAMPERED
        report_reason = chain.reason or reason or "integrity proof failed"
        if not chain.ok:
            report_reason = chain.reason or "chain verification failed"
        elif reason:
            report_reason = reason
        return VerificationReport(
            status=status,
            scope=scope,
            chain_ok=chain.ok,
            merkle_ok=merkle_ok,
            signature_ok=signature_ok,
            key_id=key_id,
            verified_at=verified_at,
            missing_events=missing,
            hash_failures=chain.hash_failures,
            reason=report_reason,
        )

    content_ok, content_reason = _verify_content_refs(events, content_store)
    if not content_ok:
        tampered = "mismatch" in content_reason
        return VerificationReport(
            status=VerificationStatus.TAMPERED if tampered else VerificationStatus.INCOMPLETE,
            scope=scope,
            chain_ok=True,
            merkle_ok=merkle_ok,
            signature_ok=signature_ok,
            key_id=key_id,
            verified_at=verified_at,
            missing_events=missing,
            reason=content_reason,
            content_ok=False,
        )

    if missing:
        return VerificationReport(
            status=VerificationStatus.INCOMPLETE,
            scope=scope,
            chain_ok=True,
            merkle_ok=merkle_ok,
            signature_ok=signature_ok,
            key_id=key_id,
            verified_at=verified_at,
            missing_events=missing,
            reason="required events missing",
        )

    if EventType.TRANSACTION_FAILED in present and EventType.TRANSACTION_COMPLETED not in present:
        return VerificationReport(
            status=VerificationStatus.FAILED,
            scope=scope,
            chain_ok=True,
            merkle_ok=merkle_ok,
            signature_ok=signature_ok,
            key_id=key_id,
            verified_at=verified_at,
            missing_events=missing,
            reason="transaction failed",
        )

    return VerificationReport(
        status=VerificationStatus.VERIFIED,
        scope=scope,
        chain_ok=True,
        merkle_ok=merkle_ok,
        signature_ok=signature_ok,
        key_id=key_id,
        verified_at=verified_at,
        missing_events=[],
    )
