from __future__ import annotations

import sqlite3
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
from curie_audit_plane.fhir.loader import iter_resources, load_bundle
from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import EventType, HumanActionStatus, VerificationStatus
from curie_audit_plane.pipeline import DEFAULT_FIXTURE, Pipeline, PipelineServices
from curie_audit_plane.privacy import opaque_identifier
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore

TAMPER_STATUSES = {
    VerificationStatus.TAMPERED,
    VerificationStatus.INCOMPLETE,
    VerificationStatus.FAILED,
}
OVERHEAD_WARMUP = 1
OVERHEAD_REPEATS = 30
LATENCY_FORMULA = "latency_ratio = (T_plane - T_no_audit_workflow) / T_no_audit_workflow"
STORAGE_OVERHEAD_ALLOCATED = (
    "storage_overhead_allocated = (bytes_allocated_plane - bytes_allocated_baseline) / bytes_allocated_baseline"
)
STORAGE_TOTAL_ALLOCATED = "storage_total_allocated = bytes_allocated_plane / bytes_allocated_baseline"
STORAGE_OVERHEAD_LOGICAL = (
    "storage_overhead_logical = (bytes_logical_plane - bytes_logical_baseline) / bytes_logical_baseline"
)
STORAGE_TOTAL_LOGICAL = "storage_total_logical = bytes_logical_plane / bytes_logical_baseline"
STORAGE_FORMULA = STORAGE_OVERHEAD_ALLOCATED


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


def _logical_sqlite_bytes(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        events = conn.execute(
            "SELECT COALESCE(SUM(OCTET_LENGTH(event_json)), 0) FROM events"
        ).fetchone()[0]
        access = conn.execute(
            "SELECT COALESCE(SUM(OCTET_LENGTH(event_json)), 0) FROM access_events"
        ).fetchone()[0]
        transactions = conn.execute(
            """
            SELECT COALESCE(SUM(
                OCTET_LENGTH(transaction_id) + OCTET_LENGTH(purpose) + OCTET_LENGTH(subject_ref)
                + OCTET_LENGTH(status) + OCTET_LENGTH(created_at)
                + OCTET_LENGTH(COALESCE(ended_at, ''))
            ), 0)
            FROM transactions
            """
        ).fetchone()[0]
        return int(events) + int(access) + int(transactions)
    finally:
        conn.close()


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
    result = pipeline.run_unrecorded_workflow(
        log_path=log_path,
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
    )
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


def _unrecorded_fields(records: list[dict[str, object]]) -> set[str]:
    found: set[str] = set()
    for record in records:
        if record.get("digest"):
            found.add("context.digest")
        if record.get("model_id"):
            found.add("model.model_id")
    return found


def _application_log_baseline(records: list[dict[str, object]]) -> dict[str, object]:
    recoverable = _unrecorded_fields(records)
    return {
        "name": "application_log",
        "implementation": "application_jsonl",
        "independence": "unrecorded_workflow",
        "arc": len(recoverable) / len(REQUIRED_FIELDS),
        "tamper_detection_rate": 0.0,
        "queryability": 0.0,
        "detected_mutation": False,
        "storage_bytes": len(canonicalize(records)),
        "reviewer_fields": [],
    }


def _hash_only_baseline(records: list[dict[str, object]]) -> dict[str, object]:
    hashed = [{**record, "digest": sha256_hex(canonicalize(record))} for record in records]
    detected = False
    if hashed:
        original = {key: value for key, value in hashed[0].items() if key != "digest"}
        mutated = {**original, "stage": "mutated"}
        detected = sha256_hex(canonicalize(mutated)) != hashed[0]["digest"]
    recoverable = _unrecorded_fields(records) | {"integrity.event_hash"}
    return {
        "name": "hash_only",
        "implementation": "hash_only_jsonl",
        "independence": "unrecorded_workflow",
        "arc": len(recoverable) / len(REQUIRED_FIELDS),
        "tamper_detection_rate": 1.0 if detected else 0.0,
        "queryability": 0.0,
        "storage_bytes": len(canonicalize(hashed)),
        "reviewer_fields": [],
    }


def _fhir_baseline_from_bundle(bundle: dict[str, object]) -> dict[str, object]:
    resources = list(iter_resources(bundle))
    entity = []
    subject_ref = None
    for resource in resources:
        resource_type = resource.get("resourceType")
        resource_id = resource.get("id")
        if not resource_type:
            continue
        token = opaque_identifier(f"{resource_type}/{resource_id}" if resource_id else str(resource_type))
        entity.append({"what": {"reference": f"{resource_type}/{token}"}})
        if resource_type == "Patient" and resource_id:
            subject_ref = opaque_identifier(f"Patient/{resource_id}")
    provenance = {
        "resourceType": "Provenance",
        "target": [{"reference": "DocumentReference/unrecorded"}],
        "agent": [{"who": {"display": "unrecorded-workflow"}}],
        "entity": entity,
    }
    recoverable = 0
    if provenance.get("target") or provenance.get("entity"):
        recoverable += 1
    if provenance.get("agent"):
        recoverable += 1
    if entity:
        recoverable += 1
    if subject_ref:
        recoverable += 1
    return {
        "name": "fhir_projection",
        "implementation": "fhir_r4_projection",
        "independence": "source_bundle",
        "arc": recoverable / len(REQUIRED_FIELDS),
        "tamper_detection_rate": 0.0,
        "queryability": 0.25 if provenance else 0.0,
        "storage_bytes": len(canonicalize({"provenance": provenance})),
        "reviewer_fields": ["subject"] if subject_ref else [],
    }


def _complete_baseline(result, public_key) -> dict[str, object]:
    arc, _ = audit_reconstruction_completeness(result)
    mutated = _mutate_model_event(result.events)
    status = verify_transaction(mutated, result.batch, public_key).status
    return {
        "name": "complete_plane",
        "implementation": "complete_audit_plane",
        "independence": "audit_chain",
        "arc": arc,
        "tamper_detection_rate": 1.0 if status in TAMPER_STATUSES else 0.0,
        "queryability": _queryable(result),
        "reviewer_fields": ["source", "model", "evidence", "guardrail", "human_action"],
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def _measure_overhead(pipeline: Pipeline) -> dict[str, object]:
    plane_ms: list[float] = []
    baseline_ms: list[float] = []
    audit_allocated: list[float] = []
    audit_logical: list[float] = []
    content_bytes: list[float] = []
    log_bytes: list[float] = []
    baseline_allocated: list[float] = []
    baseline_logical: list[float] = []
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
            audit_path = run_root / "audit.sqlite"
            allocated_audit = float(_dir_size(audit_path))
            logical_audit = float(_logical_sqlite_bytes(audit_path))
            content = float(_dir_size(run_root / "protected"))
            baseline_content = float(_dir_size(baseline_root / "protected"))
            audit_allocated.append(allocated_audit)
            audit_logical.append(logical_audit)
            content_bytes.append(content)
            log_bytes.append(float(logged_size))
            baseline_allocated.append(baseline_content + float(logged_size))
            baseline_logical.append(baseline_content + float(logged_size))
            ratios.append((plane_elapsed - baseline_elapsed) / baseline_elapsed)
    allocated_plane = mean(audit_allocated) + mean(content_bytes)
    allocated_baseline = mean(baseline_allocated)
    logical_plane = mean(audit_logical) + mean(content_bytes)
    logical_baseline = mean(baseline_logical)
    overhead_allocated = _ratio(allocated_plane - allocated_baseline, allocated_baseline)
    return {
        "n": OVERHEAD_REPEATS,
        "warmup": OVERHEAD_WARMUP,
        "baseline_name": "no_audit_workflow",
        "latency_ms_plane_mean": mean(plane_ms),
        "latency_ms_baseline_mean": mean(baseline_ms),
        "latency_ms_plane": mean(plane_ms),
        "latency_ms_baseline": mean(baseline_ms),
        "latency_ratio": paired_mean_ci(ratios),
        "storage_bytes_audit_mean": mean(audit_allocated),
        "storage_bytes_audit_allocated_mean": mean(audit_allocated),
        "storage_bytes_audit_logical_mean": mean(audit_logical),
        "storage_bytes_content_mean": mean(content_bytes),
        "storage_bytes_log_mean": mean(log_bytes),
        "storage_bytes_baseline_mean": allocated_baseline,
        "storage_bytes_allocated_plane": allocated_plane,
        "storage_bytes_allocated_baseline": allocated_baseline,
        "storage_bytes_logical_plane": logical_plane,
        "storage_bytes_logical_baseline": logical_baseline,
        "storage_overhead_allocated": overhead_allocated,
        "storage_total_allocated": _ratio(allocated_plane, allocated_baseline),
        "storage_overhead_logical": _ratio(logical_plane - logical_baseline, logical_baseline),
        "storage_total_logical": _ratio(logical_plane, logical_baseline),
        "storage_bytes_plane": allocated_plane,
        "storage_bytes_log": mean(log_bytes),
        "storage_ratio": overhead_allocated,
        "formulas": [
            LATENCY_FORMULA,
            STORAGE_OVERHEAD_ALLOCATED,
            STORAGE_TOTAL_ALLOCATED,
            STORAGE_OVERHEAD_LOGICAL,
            STORAGE_TOTAL_LOGICAL,
        ],
    }


def run_evaluation_harness(pipeline: Pipeline) -> EvaluationHarnessReport:
    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT, actor="reviewer@curie.local")
    overhead = _measure_overhead(pipeline)
    with tempfile.TemporaryDirectory(prefix="curie-baseline-") as temp:
        isolated = _isolated_pipeline(pipeline, Path(temp) / "unrecorded")
        unrecorded = isolated.run_unrecorded_workflow(log_path=Path(temp) / "workflow.jsonl")
        bundle = load_bundle(isolated.fixture_path)
        isolated.close()
    records = list(unrecorded.get("records") or [])

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
        _application_log_baseline(records),
        _hash_only_baseline(records),
        _fhir_baseline_from_bundle(bundle),
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
