from dataclasses import dataclass
from typing import Any

from curie_audit_plane.fhir.loader import iter_resources
from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.models.manifests import TransformationRecord
from curie_audit_plane.store.content import ProtectedContentStore

RESOURCE_ORDER = [
    "Patient",
    "Encounter",
    "Condition",
    "MedicationRequest",
    "Observation",
    "DiagnosticReport",
]
ALLOWED_TYPES = set(RESOURCE_ORDER)


@dataclass(frozen=True)
class ContextManifest:
    content_ref: str
    digest: str
    serialization: str = "application/json"


def _store_json(store: ProtectedContentStore, value: object, media_type: str) -> tuple[str, str]:
    payload = canonicalize(value)
    ref = store.put(payload, media_type)
    return ref, store.digest_of(payload)


def _record(
    *,
    name: str,
    version: str,
    params: dict[str, object],
    inputs: list[Any],
    outputs: object,
    store: ProtectedContentStore,
) -> TransformationRecord:
    input_refs = [_store_json(store, item, "application/fhir+json")[0] for item in inputs]
    output_ref, output_digest = _store_json(store, outputs, "application/json")
    return TransformationRecord(
        operation_id=name,
        operation_name=name,
        code_version=version,
        parameters_digest=sha256_hex(canonicalize(params)),
        input_refs=input_refs,
        output_ref=output_ref,
        output_digest=output_digest,
    )


def _normalize_resource(resource: dict[str, Any]) -> dict[str, Any]:
    clone = resource
    for key in ("code", "medicationCodeableConcept"):
        concept = clone.get(key)
        if isinstance(concept, dict) and not concept.get("text"):
            coding = concept.get("coding") or []
            if coding and isinstance(coding[0], dict):
                concept = {**concept, "text": coding[0].get("display") or coding[0].get("code")}
                clone = {**clone, key: concept}
    return clone


def apply_transformations(
    bundle: dict[str, Any],
    store: ProtectedContentStore,
) -> list[TransformationRecord]:
    resources = iter_resources(bundle)
    filtered = [resource for resource in resources if resource.get("resourceType") in ALLOWED_TYPES]
    records = [
        _record(
            name="filter_resource_types",
            version="filter.v1",
            params={"keep": RESOURCE_ORDER},
            inputs=resources,
            outputs=filtered,
            store=store,
        )
    ]
    normalized = [_normalize_resource(resource) for resource in filtered]
    records.append(
        _record(
            name="normalize_codes",
            version="normalize.v1",
            params={"rule": "fill_code_text"},
            inputs=filtered,
            outputs=normalized,
            store=store,
        )
    )
    ordered = sorted(
        normalized,
        key=lambda resource: (
            RESOURCE_ORDER.index(resource["resourceType"])
            if resource.get("resourceType") in ALLOWED_TYPES
            else 99,
            str(resource.get("id", "")),
        ),
    )
    records.append(
        _record(
            name="order_context_window",
            version="order.v1",
            params={"order": RESOURCE_ORDER},
            inputs=normalized,
            outputs=ordered,
            store=store,
        )
    )
    return records


def build_context(bundle: dict[str, Any], store: ProtectedContentStore) -> ContextManifest:
    records = apply_transformations(bundle, store)
    last = records[-1]
    return ContextManifest(content_ref=last.output_ref, digest=last.output_digest)
