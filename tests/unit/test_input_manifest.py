import json
from pathlib import Path

import pytest

from curie_audit_plane.fhir.loader import build_input_manifest, load_bundle
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.store.content import ProtectedContentStore

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/fhir/synthetic-encounter-bundle.json"


def test_input_manifest_covers_every_bundle_resource(tmp_path):
    bundle = load_bundle(FIXTURE)
    store = ProtectedContentStore(tmp_path / "protected")
    manifest = build_input_manifest(bundle, store, source_system="curie-fhir-fixture")
    resource_ids = {item.resource_id for item in manifest}
    assert resource_ids == {
        "TEST-00001",
        "enc-TEST-00001",
        "cond-htn-TEST-00001",
        "med-lisinopril-TEST-00001",
        "obs-bp-TEST-00001",
        "obs-hr-TEST-00001",
        "dx-lipid-TEST-00001",
    }
    assert all(item.source_system == "curie-fhir-fixture" for item in manifest)
    for item in manifest:
        payload = store.get(item.content_ref)
        assert item.digest == sha256_hex(payload)
        assert b"resourceType" in payload


def test_empty_or_non_patient_bundle_is_rejected(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"resourceType": "Bundle", "type": "collection", "entry": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="no entries"):
        load_bundle(empty)
    missing_patient = tmp_path / "no-patient.json"
    missing_patient.write_text(
        json.dumps(
            {
                "resourceType": "Bundle",
                "type": "collection",
                "entry": [{"resource": {"resourceType": "Observation", "id": "obs-1"}}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Patient"):
        load_bundle(missing_patient)
