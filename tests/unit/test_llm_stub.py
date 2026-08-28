from curie_audit_plane.adapters.llm_stub import stub_complete
from curie_audit_plane.models.manifests import StructuredRationale


def test_stub_is_deterministic_for_same_inputs():
    first = stub_complete("ctx-aaa", prompt_version="clinical-summary.v1")
    second = stub_complete("ctx-aaa", prompt_version="clinical-summary.v1")
    assert first.output == second.output
    assert first.manifest.prompt_version == "clinical-summary.v1"


def test_different_prompt_versions_produce_distinguishable_manifests():
    first = stub_complete("ctx-aaa", prompt_version="clinical-summary.v1")
    second = stub_complete("ctx-aaa", prompt_version="clinical-summary.v2")
    assert first.manifest.prompt_version != second.manifest.prompt_version
    assert first.output.summary != second.output.summary


def test_stub_output_matches_rationale_schema():
    result = stub_complete("ctx-aaa")
    parsed = StructuredRationale.model_validate(result.output.model_dump())
    assert parsed.findings
    assert parsed.evidence_references
    assert parsed.uncertainty
    assert "chain_of_thought" not in parsed.model_dump()
