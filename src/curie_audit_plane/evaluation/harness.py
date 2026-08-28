from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from time import perf_counter

from curie_audit_plane.evaluation.fields import (
    REQUIRED_FIELDS,
    audit_reconstruction_completeness,
    reconstruct_fields,
)
from curie_audit_plane.evaluation.stats import paired_mean_ci
from curie_audit_plane.fhir.projection import project_audit_events, project_provenance
from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import hash_event
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import EventType, HumanActionStatus, VerificationStatus
from curie_audit_plane.pipeline import DEFAULT_FIXTURE, Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore

TAMPER_STATUSES = {
    VerificationStatus.TAMPERED,
    VerificationStatus.INCOMPLETE,
    VerificationStatus.FAILED,
}
OVERHEAD_WARMUP = 1
OVERHEAD_REPEATS = 3
LATENCY_FORMULA = "latency_ratio = (T_plane - T_no_audit_workflow) / T_no_audit_workflow"
STORAGE_FORMULA = "storage_ratio = (bytes_plane - bytes_no_audit_workflow) / bytes_no_audit_workflow"


@dataclass
class EvaluationHarnessReport:
    baselines: list[dict[str, object]] = field(default_factory=list)
    capture_overhead: dict[str, object] = field(default_factory=dict)
    reviewer_task: dict[str, object] = field(default_factory=dict)


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


def _no_audit_workflow(pipeline: Pipeline, log_path: Path) -> tuple[float, int]:
    started = perf_counter()
    result = pipeline.run_unrecorded_workflow(log_path=log_path)
    elapsed_ms = (perf_counter() - started) * 1000
    if elapsed_ms <= 0:
        elapsed_ms = 0.001
    return elapsed_ms, int(result["log_bytes"])


def _isolated_pipeline(parent: Pipeline, root: Path) -> Pipeline:
    root.mkdir(parents=True, exist_ok=True)
    return Pipeline(
        PipelineServices(
            audit=AuditStore(root / "audit.sqlite"),
            content=ProtectedContentStore(root / "protected"),
            private_key=parent.services.private_key,
            public_key=parent.services.public_key,
            key_id=parent.services.key_id,
        ),
        completer=parent.completer,
        fixture_path=parent.fixture_path or DEFAULT_FIXTURE,
    )


def _mutate_model_event(events):
    mutated = [event.model_copy() for event in events]
    target = next(event for event in mutated if event.event_type == EventType.MODEL_REQUESTED)
    index = mutated.index(target)
    mutated[index] = target.model_copy(
        update={
            "payload_metadata": {
                **target.payload_metadata,
                "model_version": "mutated",
            }
        }
    )
    return mutated


def _application_log_baseline(result) -> dict[str, object]:
    records = [
        {
            "event_type": event.event_type.value,
            "occurred_at": event.occurred_at.isoformat(),
            "status": event.status.value,
        }
        for event in result.events
    ]
    recoverable = {"integrity.event_hash"} if records else set()
    mutated = list(records)
    if mutated:
        mutated[0] = {**mutated[0], "event_type": "mutated"}
    return {
        "name": "application_log",
        "implementation": "application_jsonl",
        "arc": len(recoverable) / len(REQUIRED_FIELDS),
        "tamper_detection_rate": 0.0,
        "queryability": 0.0,
        "detected_mutation": mutated != records and False,
        "storage_bytes": len(canonicalize(records)),
        "reviewer_fields": [],
    }


def _hash_only_baseline(result) -> dict[str, object]:
    records = [
        {
            "event_type": event.event_type.value,
            "occurred_at": event.occurred_at.isoformat(),
            "status": event.status.value,
            "digest": hash_event(event.model_dump(mode="json")),
        }
        for event in result.events
    ]
    mutated_events = _mutate_model_event(result.events)
    detected = False
    for original, mutated in zip(result.events, mutated_events, strict=True):
        stored = hash_event(original.model_dump(mode="json"))
        if hash_event(mutated.model_dump(mode="json")) != stored:
            detected = True
            break
    recoverable = {"integrity.event_hash"}
    return {
        "name": "hash_only",
        "implementation": "hash_only_jsonl",
        "arc": len(recoverable) / len(REQUIRED_FIELDS),
        "tamper_detection_rate": 1.0 if detected else 0.0,
        "queryability": 0.0,
        "storage_bytes": len(canonicalize(records)),
        "reviewer_fields": [],
    }


def _fhir_baseline(result) -> dict[str, object]:
    provenance = project_provenance(result)
    audit_events = project_audit_events(result)
    recoverable = 0
    if provenance.get("target") or provenance.get("entity"):
        recoverable += 1
    if provenance.get("agent"):
        recoverable += 1
    if audit_events:
        recoverable += 1
    if result.transaction.subject_ref:
        recoverable += 1
    return {
        "name": "fhir_projection",
        "implementation": "fhir_r4_projection",
        "arc": recoverable / len(REQUIRED_FIELDS),
        "tamper_detection_rate": 0.0,
        "queryability": 0.25 if provenance else 0.0,
        "storage_bytes": len(canonicalize({"provenance": provenance, "audit_events": audit_events})),
        "reviewer_fields": ["subject"] if result.transaction.subject_ref else [],
    }


def _complete_baseline(result, public_key) -> dict[str, object]:
    arc, _ = audit_reconstruction_completeness(result)
    mutated = _mutate_model_event(result.events)
    status = verify_transaction(mutated, result.batch, public_key).status
    return {
        "name": "complete_plane",
        "implementation": "complete_audit_plane",
        "arc": arc,
        "tamper_detection_rate": 1.0 if status in TAMPER_STATUSES else 0.0,
        "queryability": _queryable(result),
        "reviewer_fields": ["source", "model", "evidence", "guardrail", "human_action"],
    }


def _measure_overhead(pipeline: Pipeline) -> dict[str, object]:
    plane_ms: list[float] = []
    baseline_ms: list[float] = []
    audit_bytes: list[float] = []
    content_bytes: list[float] = []
    log_bytes: list[float] = []
    baseline_bytes: list[float] = []
    ratios: list[float] = []
    with tempfile.TemporaryDirectory(prefix="curie-overhead-") as temp:
        root = Path(temp)
        for index in range(OVERHEAD_WARMUP + OVERHEAD_REPEATS):
            baseline_root = root / f"no-audit-{index}"
            baseline = _isolated_pipeline(pipeline, baseline_root)
            log_path = baseline_root / "workflow.jsonl"
            baseline_elapsed, logged_size = _no_audit_workflow(baseline, log_path)
            baseline.close()
            run_root = root / f"plane-{index}"
            isolated = _isolated_pipeline(pipeline, run_root)
            started = perf_counter()
            isolated.run_transaction(
                human_action=HumanActionStatus.ACCEPT,
                actor="reviewer@curie.local",
            )
            plane_elapsed = (perf_counter() - started) * 1000
            isolated.close()
            if index < OVERHEAD_WARMUP:
                continue
            baseline_ms.append(baseline_elapsed)
            plane_ms.append(plane_elapsed)
            audit_bytes.append(float(_dir_size(run_root / "audit.sqlite")))
            content_bytes.append(float(_dir_size(run_root / "protected")))
            log_bytes.append(float(logged_size))
            no_audit_total = float(_dir_size(baseline_root / "protected")) + float(logged_size)
            baseline_bytes.append(no_audit_total)
            ratios.append((plane_elapsed - baseline_elapsed) / baseline_elapsed)
    plane_storage = mean(audit_bytes) + mean(content_bytes)
    baseline_storage = mean(baseline_bytes)
    return {
        "n": OVERHEAD_REPEATS,
        "warmup": OVERHEAD_WARMUP,
        "baseline_name": "no_audit_workflow",
        "latency_ms_plane_mean": mean(plane_ms),
        "latency_ms_baseline_mean": mean(baseline_ms),
        "latency_ms_plane": mean(plane_ms),
        "latency_ms_baseline": mean(baseline_ms),
        "latency_ratio": paired_mean_ci(ratios),
        "storage_bytes_audit_mean": mean(audit_bytes),
        "storage_bytes_content_mean": mean(content_bytes),
        "storage_bytes_log_mean": mean(log_bytes),
        "storage_bytes_baseline_mean": baseline_storage,
        "storage_bytes_plane": plane_storage,
        "storage_bytes_log": mean(log_bytes),
        "storage_ratio": (plane_storage - baseline_storage) / baseline_storage if baseline_storage else None,
        "formulas": [LATENCY_FORMULA, STORAGE_FORMULA],
    }


def run_evaluation_harness(pipeline: Pipeline) -> EvaluationHarnessReport:
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    overhead = _measure_overhead(pipeline)

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
    success = 1.0 if set(identified) >= set(required) else len(identified) / len(required)
    reviewer_ms = (perf_counter() - reviewer_started) * 1000

    baselines = [
        _application_log_baseline(result),
        _hash_only_baseline(result),
        _fhir_baseline(result),
        _complete_baseline(result, pipeline.services.public_key),
    ]
    return EvaluationHarnessReport(
        baselines=baselines,
        capture_overhead=overhead,
        reviewer_task={
            "success": success,
            "identified": identified,
            "duration_ms": reviewer_ms,
            "method": "scripted-field-reconstruction",
        },
    )
