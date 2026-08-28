from pathlib import Path

from curie_audit_plane.adapters.retrieval import lookup_tool, retrieve_evidence
from curie_audit_plane.fhir.loader import load_bundle
from curie_audit_plane.store.content import ProtectedContentStore

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/fhir/synthetic-encounter-bundle.json"
CORPUS = Path(__file__).resolve().parents[2] / "fixtures/corpus/clinical-knowledge.v1.json"


def test_retrieval_returns_versioned_chunks_with_digests(tmp_path):
    bundle = load_bundle(FIXTURE)
    store = ProtectedContentStore(tmp_path / "protected")
    items = retrieve_evidence(bundle, CORPUS, store)
    assert items
    assert all(item.corpus_version == "clinical-knowledge.v1" for item in items)
    assert all(item.digest for item in items)
    assert {item.chunk_id for item in items} >= {"htn-bp-target.v1"}


def test_tool_call_records_sanitized_args_and_result_digest(tmp_path):
    store = ProtectedContentStore(tmp_path / "protected")
    record = lookup_tool("htn-bp-target.v1", CORPUS, store)
    assert record.tool_id == "knowledge.lookup"
    assert record.sanitized_arguments == {"chunk_id": "htn-bp-target.v1"}
    assert "text" not in record.sanitized_arguments
    assert record.result_ref and record.result_digest
    assert store.get(record.result_ref)
