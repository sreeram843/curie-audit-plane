from curie_audit_plane.models.event import AuditEventRecord
from curie_audit_plane.stages import stage_for

STAGE_FLOW = [
    "fhir_inputs",
    "transformations",
    "context",
    "retrieval_tools",
    "model",
    "structured_output",
    "guardrails",
    "human_action",
    "integrity_proof",
]

CAPTION = (
    "Recorded artifact flow (edge width = artifact count). "
    "Width does not imply causal influence."
)


def _handoff_event_ids(
    events: list[AuditEventRecord],
    source_id: str,
    target_id: str,
) -> list[str]:
    ordered = sorted(events, key=lambda event: event.sequence_number)
    ids: list[str] = []
    seen: set[str] = set()
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if stage_for(previous.event_type.value) == source_id and stage_for(current.event_type.value) == target_id:
            for event in (previous, current):
                if event.event_id not in seen:
                    seen.add(event.event_id)
                    ids.append(event.event_id)
    return ids


def sankey_view(events: list[AuditEventRecord]) -> dict[str, object]:
    nodes = []
    for node_id in STAGE_FLOW:
        event_ids = [event.event_id for event in events if stage_for(event.event_type.value) == node_id]
        nodes.append(
            {
                "id": node_id,
                "label": node_id.replace("_", " "),
                "artifact_count": len(event_ids),
                "event_ids": event_ids,
            }
        )
    edges = []
    for index in range(len(nodes) - 1):
        source_id = nodes[index]["id"]
        target_id = nodes[index + 1]["id"]
        event_ids = _handoff_event_ids(events, source_id, target_id)
        if not event_ids:
            continue
        edges.append(
            {
                "source": source_id,
                "target": target_id,
                "value": len(event_ids),
                "metric": "artifact_count",
                "event_ids": event_ids,
            }
        )
    return {
        "metric": "artifact_count",
        "caption": CAPTION,
        "nodes": nodes,
        "edges": edges,
        "tabular_fallback": [
            {
                "stage": node["id"],
                "label": node["label"],
                "artifact_count": node["artifact_count"],
                "event_ids": node["event_ids"],
            }
            for node in nodes
        ],
        "tabular_fallback_edges": [
            {
                "source": edge["source"],
                "target": edge["target"],
                "artifact_count": edge["value"],
                "event_ids": edge["event_ids"],
            }
            for edge in edges
        ],
    }
