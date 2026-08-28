from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from curie_audit_plane.evaluation.fields import (
    audit_reconstruction_completeness,
    required_event_completeness,
)
from curie_audit_plane.integrity.chain import link_chain
from curie_audit_plane.integrity.hashing import hash_event
from curie_audit_plane.integrity.merkle import merkle_proof, merkle_root
from curie_audit_plane.integrity.signing import generate_keypair, sign_hex
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import EventType, HumanActionStatus, VerificationStatus
from curie_audit_plane.models.manifests import IntegrityBatch
from curie_audit_plane.pipeline import Pipeline

CLEAN_RUNS = 3
TAMPER_STATUSES = {
    VerificationStatus.TAMPERED,
    VerificationStatus.INCOMPLETE,
    VerificationStatus.FAILED,
}


@dataclass
class BenchmarkReport:
    clean_arc: float
    silent_missing_fields: int
    tamper_detection_rate: float
    false_tamper_rate: float
    required_event_completeness: float
    clean_case_count: int = 1
    cases: list[dict[str, object]] = field(default_factory=list)


def _batch_for(events, private_key: bytes, key_id: str) -> IntegrityBatch:
    completed = next(event for event in events if event.event_type.value == "transaction.completed")
    root = completed.event_hash
    merkle = merkle_root([root])
    proof = merkle_proof([root], 0)
    return IntegrityBatch(
        batch_id="bench-batch",
        transaction_ids=[events[0].transaction_id],
        transaction_roots=[root],
        merkle_root=merkle,
        signature=sign_hex(merkle, private_key),
        key_id=key_id,
        signed_at=datetime.now(UTC),
        inclusion_index=0,
        inclusion_proof=proof.path,
    )


def _detected(status: VerificationStatus) -> bool:
    return status in TAMPER_STATUSES


def _copy(events):
    return [event.model_copy() for event in events]


def _replace(events, event_type: EventType, **updates):
    mutated = _copy(events)
    target = next(event for event in mutated if event.event_type == event_type)
    index = mutated.index(target)
    mutated[index] = target.model_copy(update=updates)
    return mutated


def _without(events, *event_types: EventType):
    skip = set(event_types)
    return [event for event in events if event.event_type not in skip]


def _verify(events, batch, public_key, content_store=None):
    return verify_transaction(events, batch, public_key, content_store=content_store)


def _case(name: str, report, *, kind: str = "tamper") -> dict[str, object]:
    return {
        "name": name,
        "detected": _detected(report.status) if kind == "tamper" else False,
        "kind": kind,
        "chain_ok": report.chain_ok,
        "content_ok": report.content_ok,
        "status": report.status.value,
    }


def run_benchmark(pipeline: Pipeline) -> BenchmarkReport:
    cleans = [
        pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
        for _ in range(CLEAN_RUNS)
    ]
    clean = cleans[0]
    arc, missing = audit_reconstruction_completeness(clean)
    event_complete = required_event_completeness(clean)
    false_flags = sum(
        1
        for item in cleans
        if verify_transaction(item.events, item.batch, pipeline.services.public_key).status
        != VerificationStatus.VERIFIED
    )
    events = list(clean.events)
    private_key = pipeline.services.private_key
    public_key = pipeline.services.public_key
    key_id = pipeline.services.key_id
    content = pipeline.services.content
    batch = _batch_for(events, private_key, key_id)

    mutated = _copy(events)
    mutated[4] = mutated[4].model_copy(update={"payload_metadata": {"model_version": "mutated"}})
    deleted = events[:6] + events[7:]
    reordered = list(events)
    reordered[2], reordered[3] = reordered[3], reordered[2]
    broken_ref = _copy(events)
    target = next(event for event in broken_ref if event.payload_digest)
    index = broken_ref.index(target)
    broken_ref[index] = target.model_copy(update={"payload_digest": "00" * 32})
    broken_ref[index] = broken_ref[index].model_copy(
        update={"event_hash": hash_event(broken_ref[index].model_dump(mode="json"))}
    )
    bad_merkle = clean.batch.model_copy(update={"inclusion_proof": ["ff" * 32]}) if clean.batch else None
    _, other_pub = generate_keypair()
    other = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    replay = pipeline.replay(clean.transaction.transaction_id)

    content_rehashed_events = link_chain(
        _replace(
            events,
            EventType.CONTEXT_MANIFEST_CREATED,
            payload_ref="sha256:" + "ab" * 32,
            payload_digest="ab" * 32,
        )
    )
    content_rehashed_batch = _batch_for(content_rehashed_events, private_key, key_id)
    corpus_rehashed_events = link_chain(
        _replace(
            events,
            EventType.RETRIEVAL_COMPLETED,
            payload_metadata={
                **next(
                    event.payload_metadata
                    for event in events
                    if event.event_type == EventType.RETRIEVAL_COMPLETED
                ),
                "corpus_version": "substituted.v9",
            },
        )
    )
    corpus_rehashed_batch = _batch_for(corpus_rehashed_events, private_key, key_id)

    reports = {
        "mutate": _verify(mutated, batch, public_key),
        "delete": _verify(deleted, batch, public_key),
        "reorder": _verify(reordered, batch, public_key),
        "broken_reference": _verify(broken_ref, batch, public_key),
        "bad_merkle": _verify(events, bad_merkle, public_key),
        "bad_signature": _verify(events, clean.batch, other_pub),
        "missing_event": _verify(_without(events, EventType.HUMAN_ACTION_RECORDED), batch, public_key),
        "missing_input": _verify(_without(events, EventType.INPUT_MANIFEST_CREATED), batch, public_key),
        "missing_transformation": _verify(_without(events, EventType.TRANSFORMATION_APPLIED), batch, public_key),
        "missing_evidence": _verify(_without(events, EventType.RETRIEVAL_COMPLETED), batch, public_key),
        "missing_tool": _verify(
            _without(events, EventType.TOOL_CALLED, EventType.TOOL_COMPLETED),
            batch,
            public_key,
        ),
        "missing_guardrail": _verify(_without(events, EventType.GUARDRAIL_COMPLETED), batch, public_key),
        "changed_timestamp": _verify(
            _replace(events, EventType.MODEL_REQUESTED, occurred_at=events[0].occurred_at + timedelta(hours=3)),
            batch,
            public_key,
        ),
        "reviewer_action": _verify(
            _replace(
                events,
                EventType.HUMAN_ACTION_RECORDED,
                payload_metadata={
                    **next(
                        event.payload_metadata
                        for event in events
                        if event.event_type == EventType.HUMAN_ACTION_RECORDED
                    ),
                    "action": "REJECT",
                },
            ),
            batch,
            public_key,
        ),
        "wrong_corpus": _verify(
            _replace(
                events,
                EventType.RETRIEVAL_COMPLETED,
                payload_metadata={
                    **next(
                        event.payload_metadata
                        for event in events
                        if event.event_type == EventType.RETRIEVAL_COMPLETED
                    ),
                    "corpus_version": "substituted.v9",
                },
            ),
            batch,
            public_key,
        ),
        "wrong_content_ref": _verify(
            _replace(events, EventType.CONTEXT_MANIFEST_CREATED, payload_ref="sha256:" + "ab" * 32),
            batch,
            public_key,
        ),
        "wrong_corpus_rehashed": _verify(corpus_rehashed_events, corpus_rehashed_batch, public_key, content),
        "wrong_content_ref_rehashed": _verify(
            content_rehashed_events,
            content_rehashed_batch,
            public_key,
            content,
        ),
        "proof_substitution": _verify(events, other.batch, public_key),
    }
    cases: list[dict[str, object]] = [{"name": "clean", "detected": false_flags == 0, "kind": "clean"}]
    cases.extend(_case(name, report) for name, report in reports.items())
    cases.append({"name": "replay_stub", "kind": "replay", "result": replay.result, "detected": False})
    tamper_cases = [case for case in cases if case["kind"] == "tamper"]
    return BenchmarkReport(
        clean_arc=arc,
        silent_missing_fields=len(missing),
        tamper_detection_rate=sum(1 for case in tamper_cases if case["detected"]) / len(tamper_cases),
        false_tamper_rate=false_flags / len(cleans),
        required_event_completeness=event_complete,
        clean_case_count=len(cleans),
        cases=cases,
    )
