from datetime import UTC, datetime
from typing import Any

from curie_audit_plane.models.enums import EventType
from curie_audit_plane.pipeline import TransactionResult

_AUDIT_TYPE = {
    "system": "http://terminology.hl7.org/CodeSystem/audit-event-type",
    "code": "rest",
    "display": "RESTful Operation",
}


def project_provenance(result: TransactionResult) -> dict[str, Any]:
    output_event = next(
        event for event in result.events if event.event_type == EventType.STRUCTURED_OUTPUT_VALIDATED
    )
    human = next(
        (event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED),
        None,
    )
    input_event = next(
        event for event in result.events if event.event_type == EventType.INPUT_MANIFEST_CREATED
    )
    model_event = next(
        event for event in result.events if event.event_type == EventType.MODEL_REQUESTED
    )
    resources = input_event.payload_metadata.get("resources") or []
    entities = []
    for item in resources:
        if not isinstance(item, dict):
            continue
        resource_type = str(item.get("resource_type") or "Resource")
        resource_id = str(item.get("resource_id") or "")
        entities.append(
            {
                "role": {"text": "source"},
                "what": {"reference": f"{resource_type}/{resource_id}"},
            }
        )
    if not entities:
        entities.append(
            {
                "role": {"text": "source"},
                "what": {"reference": result.transaction.subject_ref},
            }
        )
    entities.append(
        {
            "role": {"text": "model-manifest"},
            "what": {
                "identifier": {
                    "system": "https://curie.local/model-manifest",
                    "value": str(model_event.payload_metadata.get("model_id")),
                },
                "display": str(model_event.payload_metadata.get("model_version") or ""),
            },
            "extension": [
                {
                    "url": "https://curie.local/fhir/StructureDefinition/model-request-digest",
                    "valueString": str(model_event.payload_metadata.get("request_digest") or ""),
                }
            ],
        }
    )
    agents = [
        {"type": {"text": "author"}, "who": {"display": "curie-audit-plane"}},
    ]
    if human:
        agents.append(
            {
                "type": {"text": "reviewer"},
                "who": {"display": str(human.payload_metadata.get("actor") or "reviewer")},
            }
        )
    recorded = (result.transaction.ended_at or datetime.now(UTC)).isoformat()
    return {
        "resourceType": "Provenance",
        "id": f"prov-{result.transaction.transaction_id}",
        "target": [{"reference": output_event.payload_ref or f"DocumentReference/{output_event.event_id}"}],
        "recorded": recorded,
        "activity": {"text": result.transaction.purpose},
        "agent": agents,
        "entity": entities,
    }


def project_audit_events(result: TransactionResult) -> list[dict[str, Any]]:
    projections: list[dict[str, Any]] = []
    for event in result.events:
        projections.append(
            {
                "resourceType": "AuditEvent",
                "id": f"ae-{event.event_id}",
                "type": _AUDIT_TYPE,
                "subtype": [
                    {
                        "coding": [
                            {
                                "system": "https://curie.local/audit-event-type",
                                "code": event.event_type.value,
                                "display": event.event_type.value,
                            }
                        ]
                    }
                ],
                "action": "E",
                "recorded": event.occurred_at.isoformat(),
                "agent": [{"who": {"display": event.actor_service}}],
                "source": {"observer": {"display": "curie-audit-plane"}},
                "entity": [
                    {
                        "what": {"identifier": {"value": event.transaction_id}},
                        "detail": [
                            {"type": "transaction_id", "valueString": event.transaction_id},
                            {"type": "event_hash", "valueString": event.event_hash},
                            {"type": "sequence_number", "valueString": str(event.sequence_number)},
                        ],
                    }
                ],
            }
        )
    return projections
