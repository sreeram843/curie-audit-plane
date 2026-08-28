from pathlib import Path

from curie_audit_plane.fhir.context import apply_transformations, build_context
from curie_audit_plane.fhir.loader import load_bundle
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.store.content import ProtectedContentStore

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/fhir/synthetic-encounter-bundle.json"


def test_transformations_are_ordered_and_reproducible(tmp_path):
    bundle = load_bundle(FIXTURE)
    store = ProtectedContentStore(tmp_path / "protected")
    first = apply_transformations(bundle, store)
    second = apply_transformations(bundle, store)
    assert [record.operation_name for record in first] == [
        "filter_resource_types",
        "normalize_codes",
        "order_context_window",
    ]
    assert [record.output_digest for record in first] == [record.output_digest for record in second]
    context = build_context(bundle, store)
    replayed = store.get(context.content_ref)
    assert context.digest == sha256_hex(replayed)
    assert b"Patient" in replayed
    last = first[-1]
    assert last.operation_id
    assert last.input_refs
    assert last.output_ref == context.content_ref
    patient_ref = next(ref for record in first for ref in record.input_refs)
    assert store.get(patient_ref)
