from __future__ import annotations

from typing import Any

from curie_audit_plane.fhir.context import ALLOWED_TYPES
from curie_audit_plane.fhir.loader import iter_resources

_MAX_BY_TYPE = {
    "Condition": 5,
    "MedicationRequest": 5,
    "Observation": 8,
    "DiagnosticReport": 3,
}


def _reference_id(value: object) -> str:
    if isinstance(value, dict):
        return _reference_id(value.get("reference"))
    text = str(value or "")
    return text.rsplit("/", 1)[-1].removeprefix("urn:uuid:")


def _matches_resource(value: object, resource_id: str) -> bool:
    token = _reference_id(value)
    return token in {"", resource_id}


def slice_first_encounter(bundle: dict[str, Any]) -> dict[str, Any]:
    resources = iter_resources(bundle)
    patient = next(item for item in resources if item.get("resourceType") == "Patient")
    encounter = next(item for item in resources if item.get("resourceType") == "Encounter")
    encounter_id = str(encounter.get("id") or "")
    patient_id = str(patient.get("id") or "")
    selected = [patient, encounter]
    counts = {key: 0 for key in _MAX_BY_TYPE}
    for resource in resources:
        resource_type = str(resource.get("resourceType") or "")
        if resource_type not in ALLOWED_TYPES or resource_type in {"Patient", "Encounter"}:
            continue
        if not _matches_resource(resource.get("encounter"), encounter_id):
            continue
        if resource_type in _MAX_BY_TYPE and counts[resource_type] >= _MAX_BY_TYPE[resource_type]:
            continue
        if not _matches_resource(resource.get("subject"), patient_id):
            continue
        selected.append(resource)
        if resource_type in counts:
            counts[resource_type] += 1
    timestamp = bundle.get("timestamp") if isinstance(bundle.get("timestamp"), str) else "2026-01-01T00:00:00Z"
    return {
        "resourceType": "Bundle",
        "id": f"sliced-encounter-{encounter_id}",
        "type": "collection",
        "timestamp": timestamp,
        "entry": [{"resource": resource} for resource in selected],
    }
