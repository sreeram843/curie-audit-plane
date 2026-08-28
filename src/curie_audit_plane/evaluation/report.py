from __future__ import annotations

import csv
import hashlib
import io
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

from curie_audit_plane.config import settings
from curie_audit_plane.evaluation.ablation import run_ablations
from curie_audit_plane.evaluation.access import run_access_control_evaluation
from curie_audit_plane.evaluation.benchmark import run_benchmark
from curie_audit_plane.evaluation.fields import (
    REQUIRED_FIELDS,
    audit_reconstruction_completeness,
    evidence_attribution_coverage,
    independently_verified_arc,
)
from curie_audit_plane.evaluation.harness import run_evaluation_harness
from curie_audit_plane.evaluation.scenarios import run_scenario_matrix, synthea_manifest
from curie_audit_plane.evaluation.study import CohortStudyReport
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import (
    REQUIRED_SUCCESS_EVENTS,
    EventType,
    HumanActionStatus,
    VerificationStatus,
)
from curie_audit_plane.pipeline import Pipeline

REPORT_SCHEMA_VERSION = "curie-evaluation.v1.1"
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
    overhead: dict[str, object] = field(default_factory=dict)
    reviewer_task: dict[str, object] = field(default_factory=dict)
    study: dict[str, object] | None = None
    scenarios: dict[str, object] | None = None
    experiment: dict[str, object] = field(default_factory=dict)
    ablations: list[dict[str, object]] = field(default_factory=list)
    access_control: dict[str, object] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "schema_version": REPORT_SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "fixture": self.fixture,
            "runtime": self.runtime,
            "experiment": self.experiment,
            "metrics": [asdict(metric) for metric in self.metrics],
            "cases": self.cases,
            "baselines": self.baselines,
            "overhead": self.overhead,
            "reviewer_task": self.reviewer_task,
            "study": self.study,
            "scenarios": self.scenarios,
            "ablations": self.ablations,
            "access_control": self.access_control,
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
        for scenario in (self.scenarios or {}).get("scenarios", []):
            rows.append(
                {
                    "row_type": "scenario",
                    "name": scenario.get("name", ""),
                    "kind": scenario.get("forced_guardrail") or scenario.get("human_action") or "",
                    "status": scenario.get("transaction_status") or scenario.get("status") or "",
                    "value": scenario.get("arc", ""),
                    "numerator": "",
                    "denominator": "",
                    "unit": "",
                    "notes": scenario.get("notes", ""),
                    "detected": "",
                    "result": scenario.get("verification_status") or "",
                }
            )
        for ablation in self.ablations:
            rows.append(
                {
                    "row_type": "ablation",
                    "name": ablation.get("name", ""),
                    "kind": "ablation",
                    "status": "MEASURED",
                    "value": ablation.get("arc", ""),
                    "numerator": "",
                    "denominator": "",
                    "unit": "fraction",
                    "notes": ablation.get("interpretation", ""),
                    "detected": "",
                    "result": ablation.get("delta", ""),
                }
            )
        for case in (self.access_control or {}).get("cases", []):
            rows.append(
                {
                    "row_type": "access",
                    "name": case.get("name", ""),
                    "kind": "access_control",
                    "status": "PASS" if case.get("passed") else "FAIL",
                    "value": 1.0 if case.get("passed") else 0.0,
                    "numerator": case.get("observed_status", ""),
                    "denominator": case.get("expected_status", ""),
                    "unit": "http_status",
                    "notes": case.get("path", ""),
                    "detected": "",
                    "result": case.get("role", ""),
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


def _evidence_coverage(result: Any, content_store: Any) -> MetricResult:
    value, valid_claims, total = evidence_attribution_coverage(result, content_store)
    if value is None:
        return _metric("evidence_attribution_coverage", None, 0, 0, "fraction", "NOT_APPLICABLE")
    return _metric("evidence_attribution_coverage", value, valid_claims, total, "fraction")


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


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = completed.stdout.strip()
    return commit or None


def _git_dirty() -> bool:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return bool(completed.stdout.strip())


def _endpoint_class(endpoint: str, runtime: str) -> str:
    if runtime == "deterministic-stub" or str(endpoint).startswith("stub://"):
        return "deterministic-stub"
    host = urlparse(str(endpoint)).hostname or ""
    if host in {"127.0.0.1", "localhost", "::1"}:
        return "loopback"
    return "other"


def _experiment_metadata(pipeline: Pipeline, generated_at: str, result: Any) -> dict[str, object]:
    fixture_path = Path(pipeline.fixture_path)
    fixture_alias = fixture_path.stem
    digest = ""
    if fixture_path.is_file():
        digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    model_event = next(
        (event for event in result.events if event.event_type == EventType.MODEL_REQUESTED),
        None,
    )
    metadata = model_event.payload_metadata if model_event else {}
    runtime = str(metadata.get("runtime") or "deterministic-stub")
    endpoint = str(metadata.get("endpoint") or "")
    decoding = metadata.get("decoding_params") or {}
    seed = decoding.get("seed") if isinstance(decoding, dict) else None
    synthea = synthea_manifest()
    return {
        "git_commit": _git_commit(),
        "git_dirty": _git_dirty(),
        "fixture_alias": fixture_alias,
        "fixture_sha256": digest,
        "provider": metadata.get("provider_id") or settings.llm_provider,
        "configured_provider": settings.llm_provider,
        "model_id": metadata.get("model_id") or settings.llm_model,
        "prompt_version": metadata.get("prompt_version") or "clinical-summary.v1",
        "decoding_params": decoding,
        "endpoint_class": _endpoint_class(endpoint, runtime),
        "seed": seed if seed is not None else 0,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "command": "curie-audit-plane evaluate --output-dir <output-dir> --encounters N --repetitions R",
        "generated_at": generated_at,
        "synthea_license": synthea.get("license"),
        "synthea_source": synthea.get("source"),
        "synthea_generator_version": synthea.get("generator_version"),
        "synthea_population_seed": synthea.get("population_seed"),
        "synthea_modules": synthea.get("modules") or [],
        "synthea_cli": synthea.get("cli"),
        "synthea_pinned": bool(synthea.get("pinned")),
        "synthea_version": synthea.get("generator_version") or "NOT_PINNED",
    }


def build_evaluation_report(
    pipeline: Pipeline,
    *,
    cohort_study: CohortStudyReport | None = None,
) -> EvaluationReport:
    benchmark = run_benchmark(pipeline)
    harness = run_evaluation_harness(pipeline)
    scenarios = run_scenario_matrix(pipeline)
    clean_result = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
    )
    ablations = run_ablations(clean_result)
    access_control = run_access_control_evaluation(pipeline)

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
    tamper_cases = [case for case in benchmark.cases if case.get("kind") == "tamper"]
    tamper_detected = sum(1 for case in tamper_cases if case.get("detected"))
    field_presence, _ = audit_reconstruction_completeness(clean_result)
    verified_arc, _ = independently_verified_arc(pipeline, clean_result.transaction.transaction_id)
    ratio_info = harness.capture_overhead.get("latency_ratio") or {}
    latency_ratio = float(ratio_info.get("mean") if isinstance(ratio_info, dict) else ratio_info or 0.0)
    baseline_ms = float(harness.capture_overhead.get("latency_ms_baseline_mean") or 0.0)
    plane_ms = float(harness.capture_overhead.get("latency_ms_plane_mean") or 0.0)
    storage_baseline = float(
        harness.capture_overhead.get("storage_bytes_allocated_baseline")
        or harness.capture_overhead.get("storage_bytes_baseline_mean")
        or 0.0
    )
    storage_plane = float(
        harness.capture_overhead.get("storage_bytes_allocated_plane")
        or harness.capture_overhead.get("storage_bytes_plane")
        or 0.0
    )
    logical_baseline = float(harness.capture_overhead.get("storage_bytes_logical_baseline") or 0.0)
    logical_plane = float(harness.capture_overhead.get("storage_bytes_logical_plane") or 0.0)
    generated_at = datetime.now(UTC).isoformat()

    metrics = [
        _metric(
            "field_presence_arc",
            field_presence,
            round(field_presence * len(REQUIRED_FIELDS)),
            len(REQUIRED_FIELDS),
            "fraction",
            notes="Required-field presence on the in-memory transaction object.",
        ),
        _metric(
            "independently_verified_arc",
            verified_arc,
            round(verified_arc * len(REQUIRED_FIELDS)),
            len(REQUIRED_FIELDS),
            "fraction",
            notes="Required-field presence after reloading persisted records and running the in-repository verifier module. The verifier is a separate implementation in this repository, not an external auditor.",
        ),
        _metric(
            "audit_reconstruction_completeness",
            verified_arc,
            round(verified_arc * len(REQUIRED_FIELDS)),
            len(REQUIRED_FIELDS),
            "fraction",
            notes="Headline ARC equals independently_verified_arc from persisted records after the in-repository verifier succeeds.",
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
            (tamper_detected / len(tamper_cases)) if tamper_cases else None,
            tamper_detected,
            len(tamper_cases),
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
        _evidence_coverage(clean_result, pipeline.services.content),
        _human_action_capture(clean_result),
        _metric(
            "capture_overhead",
            latency_ratio,
            plane_ms - baseline_ms,
            baseline_ms,
            "latency_ratio",
            notes=(
                "latency_ratio = (T_plane - T_no_audit_workflow) / T_no_audit_workflow; "
                "storage_overhead_allocated = (bytes_allocated_plane - bytes_allocated_baseline) / bytes_allocated_baseline; "
                "storage_total_allocated = bytes_allocated_plane / bytes_allocated_baseline"
            ),
        ),
        _metric(
            "storage_overhead",
            (storage_plane - storage_baseline) / storage_baseline if storage_baseline else None,
            storage_plane - storage_baseline,
            storage_baseline,
            "relative_allocated_overhead",
            status="MEASURED" if storage_baseline else "NOT_AVAILABLE",
            notes=(
                "Allocated files including SQLite page allocation. "
                "Relative overhead is (B_plane - B_base) / B_base; "
                "total allocated multiplier is B_plane / B_base. "
                "Logical serialized bytes are reported separately."
            ),
        ),
        _metric(
            "storage_total_allocated",
            storage_plane / storage_baseline if storage_baseline else None,
            storage_plane,
            storage_baseline,
            "allocated_multiplier",
            status="MEASURED" if storage_baseline else "NOT_AVAILABLE",
            notes="Allocated file size of the complete plane divided by the unrecorded workflow.",
        ),
        _metric(
            "storage_overhead_logical",
            (logical_plane - logical_baseline) / logical_baseline if logical_baseline else None,
            logical_plane - logical_baseline,
            logical_baseline,
            "relative_logical_overhead",
            status="MEASURED" if logical_baseline else "NOT_AVAILABLE",
            notes="UTF-8 octet length of SQLite event and transaction payloads plus protected-content files, excluding page allocation.",
        ),
        _metric(
            "storage_total_logical",
            logical_plane / logical_baseline if logical_baseline else None,
            logical_plane,
            logical_baseline,
            "logical_multiplier",
            status="MEASURED" if logical_baseline else "NOT_AVAILABLE",
            notes="UTF-8 logical serialized bytes of the complete plane divided by the unrecorded workflow.",
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
        generated_at=generated_at,
        fixture="synthetic-encounter-bundle",
        runtime=_recorded_runtime(clean_result),
        metrics=metrics,
        cases=benchmark.cases,
        baselines=harness.baselines,
        overhead=harness.capture_overhead,
        reviewer_task=harness.reviewer_task,
        study=cohort_study.to_json_dict() if cohort_study else None,
        scenarios=scenarios,
        experiment=_experiment_metadata(pipeline, generated_at, clean_result),
        ablations=ablations,
        access_control=access_control,
    )
