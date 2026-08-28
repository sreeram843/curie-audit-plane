import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.models.enums import EventStatus
from curie_audit_plane.models.manifests import EvidenceItem, ToolCallRecord
from curie_audit_plane.store.content import ProtectedContentStore


def load_corpus(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def retrieve_evidence(
    bundle: dict[str, Any],
    corpus_path: Path,
    store: ProtectedContentStore,
) -> list[EvidenceItem]:
    corpus = load_corpus(corpus_path)
    haystack = json.dumps(bundle).lower()
    items: list[EvidenceItem] = []
    retrieved_at = datetime.now(UTC)
    for rank, chunk in enumerate(corpus.get("chunks", []), start=1):
        keywords = [str(keyword).lower() for keyword in chunk.get("keywords", [])]
        if keywords and not any(keyword in haystack for keyword in keywords):
            continue
        payload = canonicalize(chunk)
        ref = store.put(payload, "application/json")
        items.append(
            EvidenceItem(
                evidence_id=str(chunk["chunk_id"]),
                source_type="clinical_knowledge",
                source_ref=ref,
                corpus_id=str(corpus.get("corpus_id")),
                document_id=str(chunk.get("document_id")),
                chunk_id=str(chunk["chunk_id"]),
                corpus_version=str(corpus.get("version")),
                rank=rank,
                score=1.0,
                digest=store.digest_of(payload),
                retrieved_at=retrieved_at,
            )
        )
    return items


def lookup_tool(chunk_id: str, corpus_path: Path, store: ProtectedContentStore) -> ToolCallRecord:
    corpus = load_corpus(corpus_path)
    chunk = next(item for item in corpus["chunks"] if item["chunk_id"] == chunk_id)
    result_payload = canonicalize({"chunk_id": chunk_id, "title": chunk.get("title")})
    result_ref = store.put(result_payload, "application/json")
    return ToolCallRecord(
        tool_id="knowledge.lookup",
        tool_version="1.0.0",
        result_ref=result_ref,
        result_digest=store.digest_of(result_payload),
        status=EventStatus.RECORDED,
        sequence=1,
        sanitized_arguments={"chunk_id": chunk_id},
    )
