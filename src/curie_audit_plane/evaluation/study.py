from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, median, stdev
from time import perf_counter

from curie_audit_plane.evaluation.fields import (
    audit_reconstruction_completeness,
    required_event_completeness,
)
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import EventType, HumanActionStatus, VerificationStatus
from curie_audit_plane.pipeline import Pipeline


def _summary(values: list[float], unit: str) -> dict[str, float | int | str]:
    average = mean(values)
    margin = 0.0 if len(values) < 2 else 1.96 * stdev(values) / len(values) ** 0.5
    return {
        "mean": average,
        "median": median(values),
        "ci95_low": max(0.0, average - margin),
        "ci95_high": average + margin,
        "n": len(values),
        "unit": unit,
        "status": "MEASURED",
    }


def _content_bytes(root: Path) -> int:
    return sum(item.stat().st_size for item in root.rglob("*") if item.is_file())


def _evidence_coverage(result) -> float:
    retrieval = next(
        (event for event in result.events if event.event_type == EventType.RETRIEVAL_COMPLETED),
        None,
    )
    manifest = next(
        (event for event in result.events if event.event_type == EventType.INPUT_MANIFEST_CREATED),
        None,
    )
    valid_ids = {
        str(item) for item in (retrieval.payload_metadata.get("chunk_ids") if retrieval else []) or []
    }
    valid_ids.update(
        str(item) for item in (manifest.payload_metadata.get("resource_ids") if manifest else []) or []
    )
    findings = result.output.findings if result.output else []
    if not findings:
        return 0.0
    return sum(
        bool(finding.evidence_refs) and set(finding.evidence_refs) <= valid_ids
        for finding in findings
    ) / len(findings)


def _human_action_capture(result) -> float:
    human = next(
        (event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED),
        None,
    )
    fields = ("action", "actor", "final_output_digest")
    return float(bool(human and all(human.payload_metadata.get(field) for field in fields)))


@dataclass
class CohortStudyReport:
    encounter_count: int
    repetitions: int
    observations: list[dict[str, object]] = field(default_factory=list)
    metrics: dict[str, dict[str, float | int | str | None]] = field(default_factory=dict)

    @property
    def observation_count(self) -> int:
        return len(self.observations)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "encounter_count": self.encounter_count,
            "repetitions": self.repetitions,
            "observation_count": self.observation_count,
            "metrics": self.metrics,
            "observations": self.observations,
        }


def run_cohort_study(
    pipeline: Pipeline,
    fixture_paths: list[Path],
    *,
    repetitions: int = 1,
) -> CohortStudyReport:
    if not fixture_paths:
        raise ValueError("cohort must contain at least one fixture")
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    original_fixture = pipeline.fixture_path
    observations: list[dict[str, object]] = []
    try:
        for repetition in range(1, repetitions + 1):
            for encounter_index, fixture_path in enumerate(fixture_paths, start=1):
                pipeline.fixture_path = fixture_path
                before_bytes = _content_bytes(pipeline.services.content.root)
                started = perf_counter()
                result = pipeline.run_transaction(
                    human_action=HumanActionStatus.ACCEPT,
                    actor="reviewer@curie.local",
                )
                run_latency_ms = (perf_counter() - started) * 1000
                verification_started = perf_counter()
                verification = verify_transaction(
                    result.events,
                    result.batch,
                    pipeline.services.public_key,
                    content_store=pipeline.services.content,
                )
                verification_latency_ms = (perf_counter() - verification_started) * 1000
                arc, _ = audit_reconstruction_completeness(result)
                observations.append(
                    {
                        "encounter_index": encounter_index,
                        "repetition": repetition,
                        "transaction_id": result.transaction.transaction_id,
                        "arc": arc,
                        "independently_verified_arc": arc
                        if verification.status == VerificationStatus.VERIFIED
                        else 0.0,
                        "required_event_completeness": required_event_completeness(result),
                        "evidence_attribution_coverage": _evidence_coverage(result),
                        "human_action_capture_completeness": _human_action_capture(result),
                        "verification_status": verification.status.value,
                        "event_count": len(result.events),
                        "run_latency_ms": run_latency_ms,
                        "verification_latency_ms": verification_latency_ms,
                        "protected_bytes_added": _content_bytes(pipeline.services.content.root)
                        - before_bytes,
                    }
                )
    finally:
        pipeline.fixture_path = original_fixture

    def values(key: str) -> list[float]:
        return [float(item[key]) for item in observations]

    metrics = {
        "audit_reconstruction_completeness": _summary(values("arc"), "fraction"),
        "independently_verified_arc": _summary(values("independently_verified_arc"), "fraction"),
        "required_event_completeness": _summary(values("required_event_completeness"), "fraction"),
        "evidence_attribution_coverage": _summary(values("evidence_attribution_coverage"), "fraction"),
        "human_action_capture_completeness": _summary(
            values("human_action_capture_completeness"), "fraction"
        ),
        "run_latency": _summary(values("run_latency_ms"), "milliseconds"),
        "verification_latency": _summary(values("verification_latency_ms"), "milliseconds"),
        "protected_bytes_added": _summary(values("protected_bytes_added"), "bytes"),
        "event_count": _summary(values("event_count"), "events"),
        "tamper_detection_rate": {
            "value": None,
            "status": "REPRESENTATIVE_CASE",
            "unit": "fraction",
            "notes": "The mutation suite remains in the single-transaction benchmark.",
        },
    }
    return CohortStudyReport(
        encounter_count=len(fixture_paths),
        repetitions=repetitions,
        observations=observations,
        metrics=metrics,
    )
