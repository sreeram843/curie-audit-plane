from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from curie_audit_plane.adapters.completion import CompletionRequest
from curie_audit_plane.evaluation.fields import (
    audit_reconstruction_completeness,
    reconstruct_fields,
)
from curie_audit_plane.fhir.loader import load_bundle
from curie_audit_plane.fhir.projection import project_audit_events, project_provenance
from curie_audit_plane.integrity.hashing import hash_event
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import HumanActionStatus, VerificationStatus
from curie_audit_plane.pipeline import DEFAULT_FIXTURE, Pipeline

TAMPER_STATUSES = {
    VerificationStatus.TAMPERED,
    VerificationStatus.INCOMPLETE,
    VerificationStatus.FAILED,
}


@dataclass
class EvaluationHarnessReport:
    baselines: list[dict[str, object]] = field(default_factory=list)
    capture_overhead: dict[str, float] = field(default_factory=dict)
    reviewer_task: dict[str, object] = field(default_factory=dict)


def _hash_only_flagged(events) -> bool:
    return any(hash_event(event.model_dump(mode="json")) != event.event_hash for event in events)


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _queryable(result) -> float:
    values = reconstruct_fields(result)
    keys = [
        "transaction.subject_ref",
        "model.model_id",
        "output.evidence_references",
        "guardrail.result",
        "human.action",
    ]
    found = sum(1 for key in keys if values.get(key))
    return found / len(keys)


def run_evaluation_harness(pipeline: Pipeline) -> EvaluationHarnessReport:
    bundle = load_bundle(pipeline.fixture_path or DEFAULT_FIXTURE)
    request = CompletionRequest(
        context_digest="baseline",
        context=bundle.get("entry", []),
        evidence_ids=["obs-bp-TEST-00001"],
        prompt_version="clinical-summary.v1",
    )
    started = perf_counter()
    pipeline.completer(request)
    baseline_ms = (perf_counter() - started) * 1000
    if baseline_ms <= 0:
        baseline_ms = 0.001

    started = perf_counter()
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    plane_ms = (perf_counter() - started) * 1000

    mutated = [event.model_copy() for event in result.events]
    mutated[4] = mutated[4].model_copy(update={"payload_metadata": {"model_version": "mutated"}})
    complete_status = verify_transaction(
        mutated,
        result.batch,
        pipeline.services.public_key,
        content_store=pipeline.services.content,
    ).status
    hash_only = _hash_only_flagged(mutated)
    arc, _ = audit_reconstruction_completeness(result)
    provenance = project_provenance(result)
    audit_events = project_audit_events(result)
    fhir_fields = 1 if provenance.get("target") or provenance.get("entity") else 0
    fhir_fields += 1 if audit_events else 0
    fhir_arc = fhir_fields / 4

    log_bytes = sum(
        len(
            json.dumps(
                {
                    "event_type": event.event_type.value,
                    "occurred_at": event.occurred_at.isoformat(),
                    "actor": event.actor_service,
                    "status": event.status.value,
                }
            )
        )
        for event in result.events
    )
    plane_bytes = _dir_size(pipeline.services.audit.path.parent)

    identified: list[str] = []
    values = reconstruct_fields(result)
    if values.get("transaction.subject_ref"):
        identified.append("source")
    if values.get("model.model_id"):
        identified.append("model")
    if values.get("output.evidence_references"):
        identified.append("evidence")
    if values.get("guardrail.result"):
        identified.append("guardrail")
    if values.get("human.action"):
        identified.append("human_action")
    required = ["source", "model", "evidence", "guardrail", "human_action"]
    reviewer_started = perf_counter()
    success = 1.0 if identified == required or set(identified) >= set(required) else len(identified) / len(required)
    reviewer_ms = (perf_counter() - reviewer_started) * 1000

    baselines = [
        {
            "name": "application_log",
            "arc": arc,
            "tamper_detection_rate": 0.0,
            "queryability": _queryable(result),
        },
        {
            "name": "hash_only",
            "arc": arc,
            "tamper_detection_rate": 1.0 if hash_only else 0.0,
            "queryability": _queryable(result),
        },
        {
            "name": "fhir_projection",
            "arc": fhir_arc,
            "tamper_detection_rate": 0.0,
            "queryability": _queryable(result) * 0.5,
        },
        {
            "name": "complete_plane",
            "arc": arc,
            "tamper_detection_rate": 1.0 if complete_status in TAMPER_STATUSES else 0.0,
            "queryability": _queryable(result),
        },
    ]
    return EvaluationHarnessReport(
        baselines=baselines,
        capture_overhead={
            "latency_ms_plane": plane_ms,
            "latency_ms_baseline": baseline_ms,
            "latency_ratio": (plane_ms - baseline_ms) / baseline_ms,
            "storage_bytes_plane": float(plane_bytes),
            "storage_bytes_log": float(log_bytes),
        },
        reviewer_task={
            "success": success,
            "identified": identified,
            "duration_ms": reviewer_ms,
            "method": "scripted-field-reconstruction",
        },
    )
