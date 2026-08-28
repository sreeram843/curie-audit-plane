import json
from pathlib import Path
from typing import Any

from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.models.manifests import InputManifestItem
from curie_audit_plane.store.content import ProtectedContentStore


def load_bundle(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("resourceType") != "Bundle":
        raise ValueError("fixture must be a FHIR Bundle")
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries:
        raise ValueError("FHIR Bundle has no entries")
    resources = iter_resources(payload)
    if not resources:
        raise ValueError("FHIR Bundle has no valid resources")
    types = {str(resource.get("resourceType")) for resource in resources}
    if "Patient" not in types:
        raise ValueError("FHIR Bundle must include a Patient resource")
    return payload


def iter_resources(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") and resource.get("id"):
            resources.append(resource)
    return resources


def build_input_manifest(
    bundle: dict[str, Any],
    store: ProtectedContentStore,
    source_system: str = "curie-fhir-fixture",
) -> list[InputManifestItem]:
    items: list[InputManifestItem] = []
    timestamp = bundle.get("timestamp")
    version = timestamp if isinstance(timestamp, str) else None
    for resource in iter_resources(bundle):
        payload = canonicalize(resource)
        ref = store.put(payload, "application/fhir+json")
        items.append(
            InputManifestItem(
                resource_type=str(resource["resourceType"]),
                resource_id=str(resource["id"]),
                source_system=source_system,
                source_location=f"{source_system}:{resource['resourceType']}/{resource['id']}",
                version_or_time=version,
                selection_reason="included in requested encounter bundle",
                content_ref=ref,
                digest=store.digest_of(payload),
            )
        )
    return items
