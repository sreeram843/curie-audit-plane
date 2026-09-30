from __future__ import annotations

import hashlib
import re
from typing import Any

from curie_audit_plane.models.enums import EventType
from curie_audit_plane.pipeline import TransactionResult

_ID_RE = re.compile(r"TEST-\d{5}")
_UUID_RE = re.compile(
    r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)
_FHIR_REF_RE = re.compile(
    r"\b(?:Patient|Encounter|Condition|Observation|MedicationRequest|DiagnosticReport)/[A-Za-z0-9._-]+"
)
_PHONE_RE = re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
_DATE_ONLY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PERSON_NAME_RE = re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b")
_IDENTIFIER_KEYS = frozenset(
    {
        "actor",
        "comment",
        "display",
        "name",
        "patient_id",
        "payload_ref",
        "phone",
        "reference",
        "resource_id",
        "resource_ids",
        "source_output_id",
        "subject_ref",
        "telecom",
        "transaction_id",
        "who",
    }
)
_SALT = b"curie-audit-plane-research-v1"


def _pseudo(value: str, prefix: str) -> str:
    digest = hashlib.sha256(_SALT + value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _is_identifier_key(key: str) -> bool:
    return (
        key in _IDENTIFIER_KEYS
        or key.endswith("_id")
        or key.endswith("_ids")
        or key.endswith("_ref")
    )


def _scrub_string(value: str, tx_id: str, key: str) -> str:
    if value == tx_id:
        return _pseudo(tx_id, "tx")
    if _is_identifier_key(key):
        return _pseudo(value, "id")
    if (
        _ID_RE.search(value)
        or _UUID_RE.search(value)
        or _FHIR_REF_RE.search(value)
        or _PHONE_RE.search(value)
        or _DATE_ONLY_RE.fullmatch(value)
        or _PERSON_NAME_RE.search(value)
    ):
        return _pseudo(value, "id")
    return value


def _scrub(value: Any, tx_id: str, key: str = "") -> Any:
    if isinstance(value, str):
        return _scrub_string(value, tx_id, key)
    if isinstance(value, list):
        if _is_identifier_key(key):
            return [_pseudo(str(item), "id") for item in value]
        return [_scrub(item, tx_id, key) for item in value]
    if isinstance(value, dict):
        return {
            nested_key: _scrub(item, tx_id, nested_key)
            for nested_key, item in value.items()
            if nested_key not in {"payload", "bytes", "content", "comment"}
        }
    return value


def research_export(result: TransactionResult) -> dict[str, Any]:
    tx_id = result.transaction.transaction_id
    events = []
    for event in result.events:
        meta = {
            key: value
            for key, value in event.payload_metadata.items()
            if key
            not in {
                "comment",
                "actor",
            }
        }
        events.append(
            {
                "event_type": event.event_type.value,
                "status": event.status.value,
                "sequence_number": event.sequence_number,
                "occurred_at": event.occurred_at.isoformat(),
                "payload_digest": event.payload_digest,
                "event_hash": event.event_hash,
                "previous_event_hash": event.previous_event_hash,
                "payload_metadata": _scrub(meta, tx_id),
            }
        )
    model = next((event for event in result.events if event.event_type == EventType.MODEL_REQUESTED), None)
    guardrails = [
        {
            "rule_id": event.payload_metadata.get("rule_id"),
            "result": event.payload_metadata.get("result"),
            "scope": event.payload_metadata.get("scope"),
        }
        for event in result.events
        if event.event_type == EventType.GUARDRAIL_COMPLETED
    ]
    human = next((event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED), None)
    return {
        "export_type": "research",
        "schema_version": "1.0.0",
        "notice": (
            "De-identified research export. Raw clinical payloads and direct identifiers are excluded. "
            "Access, verification, and administrative events are omitted; only clinical pipeline events "
            "and verification summary fields are included."
        ),
        "event_inclusion": {
            "clinical_events": True,
            "access_events": False,
            "verification_summary": True,
            "administrative_events": False,
        },
        "transaction_id": _pseudo(tx_id, "tx"),
        "subject_ref": _pseudo(result.transaction.subject_ref, "subj"),
        "purpose": _pseudo(result.transaction.purpose, "purpose"),
        "status": result.transaction.status.value,
        "verification_status": result.verification.status.value,
        "verification_reason": result.verification.reason,
        "missing_events": result.verification.missing_events,
        "human_action": result.transaction.human_action.value,
        "started_at": result.transaction.started_at.isoformat(),
        "ended_at": result.transaction.ended_at.isoformat() if result.transaction.ended_at else None,
        "model": {
            "model_id": model.payload_metadata.get("model_id") if model else None,
            "model_version": model.payload_metadata.get("model_version") if model else None,
            "prompt_version": model.payload_metadata.get("prompt_version") if model else None,
            "runtime": model.payload_metadata.get("runtime") if model else None,
        },
        "guardrails": guardrails,
        "human": {
            "action": human.payload_metadata.get("action") if human else None,
            "role": human.payload_metadata.get("role") if human else None,
        },
        "events": events,
        "integrity": {
            "chain_ok": result.verification.chain_ok,
            "merkle_ok": result.verification.merkle_ok,
            "signature_ok": result.verification.signature_ok,
            "key_id": result.verification.key_id,
        },
    }
