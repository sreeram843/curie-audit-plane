from curie_audit_plane.evaluation.cohort import generate_synthetic_cohort
from curie_audit_plane.evaluation.study import run_cohort_study
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def _pipeline(tmp_path):
    private_key, public_key = generate_keypair()
    return Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="study-key",
        )
    )


def test_cohort_study_aggregates_repeated_runs_with_confidence_intervals(tmp_path):
    pipeline = _pipeline(tmp_path)
    paths = generate_synthetic_cohort(
        "fixtures/fhir/synthetic-encounter-bundle.json",
        tmp_path / "cohort",
        count=3,
    )

    study = run_cohort_study(pipeline, paths, repetitions=2)

    assert study.encounter_count == 3
    assert study.repetitions == 2
    assert study.observation_count == 6
    arc = study.metrics["audit_reconstruction_completeness"]
    assert arc["mean"] == 1.0
    assert arc["median"] == 1.0
    assert arc["interval"] == "wilson"
    assert arc["ci95_high"] == 1.0
    assert arc["ci95_low"] < 1.0
    assert study.metrics["run_latency"]["interval"] == "normal"
    assert study.metrics["tamper_detection_rate"]["status"] == "REPRESENTATIVE_CASE"
    assert study.metrics["verification_latency"]["unit"] == "milliseconds"
    assert len(study.observations) == 6
    verified = study.metrics["independently_verified_arc"]
    assert verified["mean"] == 1.0
    assert verified["interval"] == "wilson"
    pipeline.close()


def test_cohort_independently_verified_arc_reloads_persisted_records(tmp_path):
    pipeline = _pipeline(tmp_path)
    paths = generate_synthetic_cohort(
        "fixtures/fhir/synthetic-encounter-bundle.json",
        tmp_path / "cohort",
        count=2,
    )
    loads = {"n": 0}
    original = pipeline.load_result

    def counting_load(transaction_id: str):
        loads["n"] += 1
        return original(transaction_id)

    pipeline.load_result = counting_load  # type: ignore[method-assign]
    study = run_cohort_study(pipeline, paths, repetitions=1)
    assert study.observation_count == 2
    assert loads["n"] >= 2
    assert all(item["independently_verified_arc"] == 1.0 for item in study.observations)
    pipeline.close()
