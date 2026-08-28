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
    assert arc["ci95_low"] == 1.0
    assert arc["ci95_high"] == 1.0
    assert study.metrics["tamper_detection_rate"]["status"] == "REPRESENTATIVE_CASE"
    assert study.metrics["verification_latency"]["unit"] == "milliseconds"
    assert len(study.observations) == 6
    pipeline.close()
