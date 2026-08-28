import json

import pytest

from curie_audit_plane.evaluation.cohort import generate_synthetic_cohort
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore


def test_generate_synthetic_cohort_is_bounded_and_rewrites_references(tmp_path):
    paths = generate_synthetic_cohort(
        "fixtures/fhir/synthetic-encounter-bundle.json",
        tmp_path / "cohort",
        count=3,
    )

    assert len(paths) == 3
    first = json.loads(paths[0].read_text())
    third = json.loads(paths[2].read_text())
    assert first["entry"][0]["resource"]["id"] == "TEST-00001"
    assert third["entry"][0]["resource"]["id"] == "TEST-00003"
    assert third["entry"][1]["resource"]["subject"]["reference"] == "Patient/TEST-00003"
    assert third["timestamp"] == "2026-08-03T14:30:00Z"
    assert paths[0] != paths[1] != paths[2]


def test_generate_synthetic_cohort_rejects_invalid_size(tmp_path):
    with pytest.raises(ValueError, match="between 1 and 1000"):
        generate_synthetic_cohort(
            "fixtures/fhir/synthetic-encounter-bundle.json",
            tmp_path / "cohort",
            count=0,
        )


def test_scaled_encounter_keeps_output_evidence_references_valid(tmp_path):
    path = generate_synthetic_cohort(
        "fixtures/fhir/synthetic-encounter-bundle.json",
        tmp_path / "cohort",
        count=2,
    )[1]
    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
        ),
        fixture_path=path,
    )

    result = pipeline.run_transaction(human_action=HumanActionStatus.ACCEPT)

    assert "obs-bp-TEST-00002" in result.output.evidence_references
    assert "med-lisinopril-TEST-00002" in result.output.evidence_references
    pipeline.close()
