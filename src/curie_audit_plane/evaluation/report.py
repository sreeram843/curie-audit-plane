from __future__ import annotations

import csv
import io
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from curie_audit_plane.evaluation.benchmark import run_benchmark
from curie_audit_plane.evaluation.fields import REQUIRED_FIELDS
from curie_audit_plane.evaluation.harness import run_evaluation_harness
from curie_audit_plane.evaluation.study import CohortStudyReport
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import (
    REQUIRED_SUCCESS_EVENTS,
    EventType,
    HumanActionStatus,
    VerificationStatus,
)
from curie_audit_plane.pipeline import Pipeline

REPORT_SCHEMA_VERSION = "curie-evaluation.v1"
CSV_FIELDS = [
    "row_type",
    "name",
    "kind",
    "status",
    "value",
    "numerator",
    "denominator",
    "unit",
    "notes",
    "detected",
    "result",
]


@dataclass(frozen=True)
class MetricResult:
    name: str
    value: float | None
    numerator: float | None
    denominator: float | None
    unit: str
    status: str
    notes: str = ""


@dataclass
class EvaluationReport:
    generated_at: str
    fixture: str
    runtime: str
    metrics: list[MetricResult] = field(default_factory=list)
    cases: list[dict[str, object]] = field(default_factory=list)
    baselines: list[dict[str, object]] = field(default_factory=list)
    overhead: dict[str, float] = field(default_factory=dict)
    reviewer_task: dict[str, object] = field(default_factory=dict)
    study: dict[str, object] | None = None

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "fixture": self.fixture,
            "runtime": self.runtime,
            "metrics": [asdict(metric) for metric in self.metrics],
            "cases": self.cases,
            "baselines": self.baselines,
            "overhead": self.overhead,
            "reviewer_task": self.reviewer_task,
            "study": self.study,
        }

    def to_csv_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for metric in self.metrics:
            rows.append(
                {
                    "row_type": "metric",
                    "name": metric.name,
                    "kind": "",
                    "status": metric.status,
                    "value": metric.value,
                    "numerator": metric.numerator,
                    "denominator": metric.denominator,
                    "unit": metric.unit,
                    "notes": metric.notes,
                    "detected": "",
                    "result": "",
                }
            )
        if self.study:
            study_metrics = self.study.get("metrics", {})
            for name, metric in study_metrics.items():
                rows.append(
                    {
                        "row_type": "metric",
                        "name": f"cohort.{name}",
                        "kind": "cohort",
                        "status": metric.get("status", "MEASURED"),
                        "value": metric.get("mean"),
                        "numerator": "",
                        "denominator": metric.get("n", ""),
                        "unit": metric.get("unit", ""),
                        "notes": (
                            f"median={metric.get('median')}; "
                            f"ci95=[{metric.get('ci95_low')}, {metric.get('ci95_high')}]"
                        ),
                        "detected": "",
                        "result": "",
                    }
                )
        for case in self.cases:
            rows.append(
                {
                    "row_type": "case",
                    "name": case.get("name", ""),
                    "kind": case.get("kind", ""),
                    "status": "",
                    "value": "",
                    "numerator": "",
                    "denominator": "",
                    "unit": "",
                    "notes": "",
                    "detected": case.get("detected", ""),
                    "result": case.get("result", ""),
                }
            )
        return rows

    def to_csv(self) -> str:
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(self.to_csv_rows())
        return output.getvalue()


def _metric(
    name: str,
    value: float | None,
    numerator: float | None,
    denominator: float | None,
    unit: str,
    status: str = "MEASURED",
    notes: str = "",
) -> MetricResult:
    return MetricResult(name, value, numerator, denominator, unit, status, notes)


def _evidence_coverage(result: Any) -> MetricResult:
    retrieval = next(
        (event for event in result.events if event.event_type == EventType.RETRIEVAL_COMPLETED),
        None,
    )
    input_manifest = next(
        (event for event in result.events if event.event_type == EventType.INPUT_MANIFEST_CREATED),
        None,
    )
    valid_ids = {
        str(item) for item in (retrieval.payload_metadata.get("chunk_ids") if retrieval else []) or []
    }
    valid_ids.update(
        str(item)
        for item in (input_manifest.payload_metadata.get("resource_ids") if input_manifest else []) or []
    )
    findings = result.output.findings if result.output else []
    if not findings:
        return _metric("evidence_attribution_coverage", None, 0, 0, "fraction", "NOT_APPLICABLE")
    valid_claims = sum(
        bool(finding.evidence_refs) and set(finding.evidence_refs) <= valid_ids for finding in findings
    )
    return _metric(
        "evidence_attribution_coverage",
        valid_claims / len(findings),
        valid_claims,
        len(findings),
        "fraction",
    )


def _human_action_capture(result: Any) -> MetricResult:
    human = next(
        (event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED),
        None,
    )
    required = ("action", "actor", "final_output_digest")
    complete = bool(human and all(human.payload_metadata.get(field) for field in required))
    return _metric(
        "human_action_capture_completeness",
        float(complete),
        int(complete),
        1,
        "fraction",
    )


def _recorded_runtime(result: Any) -> str:
    event = next(
        (item for item in result.events if item.event_type == EventType.MODEL_REQUESTED),
        None,
    )
    runtime = event.payload_metadata.get("runtime") if event else None
    return str(runtime or "deterministic-stub")


def build_evaluation_report(
    pipeline: Pipeline,
    *,
    cohort_study: CohortStudyReport | None = None,
) -> EvaluationReport:
    benchmark = run_benchmark(pipeline)
    harness = run_evaluation_harness(pipeline)
    clean_result = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
    )

    verification_started = perf_counter()
    verification = verify_transaction(
        clean_result.events,
        clean_result.batch,
        pipeline.services.public_key,
        content_store=pipeline.services.content,
    )
    verification_ms = (perf_counter() - verification_started) * 1000

    replay_case = next((case for case in benchmark.cases if case.get("kind") == "replay"), None)
    replay_classification = str(replay_case.get("result")) if replay_case else "NOT_REPLAYABLE"
    replay_value = 1.0 if replay_classification in {"EXACT_MATCH", "EQUIVALENT"} else 0.0
    baseline_ms = harness.capture_overhead.get("latency_ms_baseline", 0.0)
    plane_ms = harness.capture_overhead.get("latency_ms_plane", 0.0)
    storage_log = harness.capture_overhead.get("storage_bytes_log", 0.0)
    storage_plane = harness.capture_overhead.get("storage_bytes_plane", 0.0)

    metrics = [
        _metric(
            "audit_reconstruction_completeness",
            benchmark.clean_arc,
            round(benchmark.clean_arc * len(REQUIRED_FIELDS)),
            len(REQUIRED_FIELDS),
            "fraction",
            notes="Current prototype field-presence ARC; independent verification is reported separately.",
        ),
        _metric(
            "required_event_completeness",
            benchmark.required_event_completeness,
            round(benchmark.required_event_completeness * len(REQUIRED_SUCCESS_EVENTS)),
            len(REQUIRED_SUCCESS_EVENTS),
            "fraction",
            notes="Successful-transaction required event presence.",
        ),
        _metric(
            "tamper_detection_rate",
            benchmark.tamper_detection_rate,
            round(benchmark.tamper_detection_rate * 12),
            12,
            "fraction",
        ),
        _metric(
            "false_tamper_rate",
            benchmark.false_tamper_rate,
            round(benchmark.false_tamper_rate * benchmark.clean_case_count),
            benchmark.clean_case_count,
            "fraction",
        ),
        _metric(
            "replay_fidelity",
            replay_value,
            replay_value,
            1,
            "fraction_exact_or_equivalent",
            notes=f"classification={replay_classification}",
        ),
        _evidence_coverage(clean_result),
        _human_action_capture(clean_result),
        _metric(
            "capture_overhead",
            harness.capture_overhead.get("latency_ratio"),
            plane_ms - baseline_ms,
            baseline_ms,
            "latency_ratio",
            notes="Compared with the same completer without audit capture; storage values are included in the report.",
        ),
        _metric(
            "storage_overhead",
            (storage_plane - storage_log) / storage_log if storage_log else None,
            storage_plane - storage_log,
            storage_log,
            "storage_ratio",
            status="MEASURED" if storage_log else "NOT_AVAILABLE",
        ),
        _metric(
            "verification_latency",
            verification_ms,
            verification_ms,
            1,
            "milliseconds",
            status="MEASURED" if verification.status == VerificationStatus.VERIFIED else "WARNING",
            notes=f"verification_status={verification.status.value}",
        ),
        _metric(
            "reviewer_task_success",
            float(harness.reviewer_task.get("success", 0.0)),
            float(len(harness.reviewer_task.get("identified", []))),
            5,
            "fraction",
            status="SCRIPTED_PROXY",
            notes="Not a human-subject usability result; scripted field reconstruction only.",
        ),
    ]
    return EvaluationReport(
        generated_at=datetime.now(UTC).isoformat(),
        fixture=str(pipeline.fixture_path),
        runtime=_recorded_runtime(clean_result),
        metrics=metrics,
        cases=benchmark.cases,
        baselines=harness.baselines,
        overhead=harness.capture_overhead,
        reviewer_task=harness.reviewer_task,
        study=cohort_study.to_json_dict() if cohort_study else None,
    )
