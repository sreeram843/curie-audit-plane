from __future__ import annotations

import json

from curie_audit_plane.models.enums import REQUIRED_SUCCESS_EVENTS, EventType, VerificationStatus
from curie_audit_plane.pipeline import Pipeline, TransactionResult
from curie_audit_plane.store.content import ProtectedContentStore

REQUIRED_FIELDS = [
    "transaction.transaction_id",
    "transaction.purpose",
    "transaction.subject_ref",
    "input.manifest.resource_ids",
    "transformation.output_digest",
    "context.digest",
    "model.model_id",
    "model.prompt_version",
    "output.digest",
    "output.uncertainty",
    "output.evidence_references",
    "guardrail.result",
    "human.action",
    "human.actor",
    "human.final_output_digest",
    "integrity.event_hash",
    "integrity.previous_event_hash",
    "integrity.merkle_root",
    "integrity.signature",
    "integrity.key_id",
]


def _event(result: TransactionResult, event_type: EventType):
    return next((event for event in result.events if event.event_type == event_type), None)


def reconstruct_fields(result: TransactionResult) -> dict[str, object | None]:
    started = _event(result, EventType.TRANSACTION_STARTED)
    manifest = _event(result, EventType.INPUT_MANIFEST_CREATED)
    transform = _event(result, EventType.TRANSFORMATION_APPLIED)
    context = _event(result, EventType.CONTEXT_MANIFEST_CREATED)
    model = _event(result, EventType.MODEL_REQUESTED)
    output = _event(result, EventType.STRUCTURED_OUTPUT_VALIDATED)
    guardrail = _event(result, EventType.GUARDRAIL_COMPLETED)
    human = _event(result, EventType.HUMAN_ACTION_RECORDED)
    proof = _event(result, EventType.INTEGRITY_PROOF_COMMITTED)
    values: dict[str, object | None] = {
        "transaction.transaction_id": result.transaction.transaction_id,
        "transaction.purpose": started.payload_metadata.get("purpose") if started else None,
        "transaction.subject_ref": started.payload_metadata.get("subject_ref") if started else None,
        "input.manifest.resource_ids": manifest.payload_metadata.get("resource_ids") if manifest else None,
        "transformation.output_digest": transform.payload_metadata.get("output_digest") if transform else None,
        "context.digest": context.payload_digest if context else None,
        "model.model_id": model.payload_metadata.get("model_id") if model else None,
        "model.prompt_version": model.payload_metadata.get("prompt_version") if model else None,
        "output.digest": output.payload_digest if output else None,
        "output.uncertainty": result.output.uncertainty if result.output else None,
        "output.evidence_references": result.output.evidence_references if result.output else None,
        "guardrail.result": guardrail.payload_metadata.get("result") if guardrail else None,
        "human.action": human.payload_metadata.get("action") if human else None,
        "human.actor": human.payload_metadata.get("actor") if human else None,
        "human.final_output_digest": human.payload_metadata.get("final_output_digest") if human else None,
        "integrity.event_hash": result.events[-1].event_hash if result.events else None,
        "integrity.previous_event_hash": result.events[-1].previous_event_hash if result.events else None,
        "integrity.merkle_root": proof.payload_metadata.get("merkle_root") if proof else None,
        "integrity.signature": proof.payload_metadata.get("signature") if proof else None,
        "integrity.key_id": proof.payload_metadata.get("key_id") if proof else None,
    }
    return values


def audit_reconstruction_completeness(result: TransactionResult) -> tuple[float, list[str]]:
    values = reconstruct_fields(result)
    missing = [name for name in REQUIRED_FIELDS if not values.get(name)]
    reconstructed = len(REQUIRED_FIELDS) - len(missing)
    return reconstructed / len(REQUIRED_FIELDS), missing


def evidence_id_universe(result: TransactionResult, content_store: ProtectedContentStore) -> set[str]:
    retrieval = _event(result, EventType.RETRIEVAL_COMPLETED)
    started = _event(result, EventType.TRANSACTION_STARTED)
    valid_ids = {
        str(item) for item in (retrieval.payload_metadata.get("chunk_ids") if retrieval else []) or []
    }
    identity_ref = started.payload_metadata.get("identity_ref") if started else None
    if identity_ref:
        identity = json.loads(content_store.get(str(identity_ref)))
        if identity.get("subject_raw"):
            raw_subject = str(identity["subject_raw"])
            valid_ids.add(raw_subject)
            valid_ids.add(raw_subject.rsplit("/", 1)[-1])
        for item in identity.get("resources") or []:
            if item.get("raw"):
                valid_ids.add(str(item["raw"]))
    return valid_ids


def evidence_attribution_coverage(
    result: TransactionResult, content_store: ProtectedContentStore
) -> tuple[float | None, int, int]:
    valid_ids = evidence_id_universe(result, content_store)
    findings = result.output.findings if result.output else []
    if not findings:
        return None, 0, 0
    valid_claims = sum(
        bool(finding.evidence_refs) and set(finding.evidence_refs) <= valid_ids for finding in findings
    )
    return valid_claims / len(findings), valid_claims, len(findings)



def independently_verified_arc(pipeline: Pipeline, transaction_id: str) -> tuple[float, list[str]]:
    reloaded = pipeline.load_result(transaction_id)
    presence, missing = audit_reconstruction_completeness(reloaded)
    if reloaded.verification.status != VerificationStatus.VERIFIED:
        return 0.0, [*missing, "verification.independent"]
    return presence, missing


def required_event_completeness(result: TransactionResult) -> float:
    present = {event.event_type for event in result.events}
    found = sum(1 for event_type in REQUIRED_SUCCESS_EVENTS if event_type in present)
    return found / len(REQUIRED_SUCCESS_EVENTS)
