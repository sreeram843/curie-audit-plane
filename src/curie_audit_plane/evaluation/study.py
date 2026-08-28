from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter

from curie_audit_plane.evaluation.fields import (
    audit_reconstruction_completeness,
    evidence_attribution_coverage,
    required_event_completeness,
)
from curie_audit_plane.evaluation.stats import summarize_values
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import EventType, HumanActionStatus, VerificationStatus
from curie_audit_plane.pipeline import Pipeline


def _content_bytes(root: Path) -> int:
    return sum(item.stat().st_size for item in root.rglob("*") if item.is_file())


def _evidence_coverage(result, content_store) -> float:
    value, _, _ = evidence_attribution_coverage(result, content_store)
    return float(value or 0.0)


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
                        "evidence_attribution_coverage": _evidence_coverage(
                            result, pipeline.services.content
                        ),
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
        "audit_reconstruction_completeness": summarize_values(values("arc"), "fraction"),
        "independently_verified_arc": summarize_values(values("independently_verified_arc"), "fraction"),
        "required_event_completeness": summarize_values(values("required_event_completeness"), "fraction"),
        "evidence_attribution_coverage": summarize_values(
            values("evidence_attribution_coverage"), "fraction"
        ),
        "human_action_capture_completeness": summarize_values(
            values("human_action_capture_completeness"), "fraction"
        ),
        "run_latency": summarize_values(values("run_latency_ms"), "milliseconds"),
        "verification_latency": summarize_values(values("verification_latency_ms"), "milliseconds"),
        "protected_bytes_added": summarize_values(values("protected_bytes_added"), "bytes"),
        "event_count": summarize_values(values("event_count"), "events"),
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
