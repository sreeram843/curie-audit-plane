from curie_audit_plane.guardrails.engine import evaluate_guardrails
from curie_audit_plane.models.enums import GuardrailStatus
from curie_audit_plane.models.manifests import Finding, StructuredRationale


def _rationale(**overrides) -> StructuredRationale:
    payload = {
        "summary": "Hypertension remains above office target.",
        "findings": [Finding(text="Office BP 148/92 mmHg", evidence_refs=["obs-bp-TEST-00001"])],
        "evidence_references": ["obs-bp-TEST-00001", "htn-bp-target.v1"],
        "uncertainty": "Single-visit measurements.",
        "assumptions": ["Medication adherence is unknown."],
        "missing_data": ["Home blood pressure series."],
        "follow_up_questions": ["Were antihypertensives taken this morning?"],
    }
    payload.update(overrides)
    return StructuredRationale.model_validate(payload)


def test_guardrails_pass_on_complete_output():
    results = evaluate_guardrails(_rationale())
    by_rule = {item.rule_id: item.result for item in results}
    assert by_rule["schema.v1"] == GuardrailStatus.PASS
    assert by_rule["evidence_refs.v1"] == GuardrailStatus.PASS
    assert by_rule["uncertainty.v1"] == GuardrailStatus.PASS


def test_missing_citations_warn_and_zero_citations_block():
    warned = evaluate_guardrails(
        _rationale(findings=[Finding(text="Unsupported claim", evidence_refs=[])])
    )
    assert any(item.rule_id == "evidence_refs.v1" and item.result == GuardrailStatus.WARN for item in warned)

    blocked = evaluate_guardrails(
        _rationale(
            findings=[Finding(text="Unsupported claim", evidence_refs=[])],
            evidence_references=[],
        )
    )
    assert any(item.rule_id == "evidence_refs.v1" and item.result == GuardrailStatus.BLOCK for item in blocked)


def test_empty_uncertainty_warns():
    results = evaluate_guardrails(_rationale(uncertainty=""))
    assert any(item.rule_id == "uncertainty.v1" and item.result == GuardrailStatus.WARN for item in results)


def test_phi_scan_warns_on_mrn_pattern():
    results = evaluate_guardrails(_rationale(summary="Patient TEST-00001 remains hypertensive."))
    assert any(item.rule_id == "phi_scan.v1" and item.result == GuardrailStatus.WARN for item in results)


def test_guardrail_scopes_are_emitted_only_when_checked():
    output_only = evaluate_guardrails(_rationale())
    scopes = {item.scope for item in output_only}
    assert "structured_output" in scopes
    assert "policy_action" in scopes
    assert "input" not in scopes
    assert "context" not in scopes
    assert "evidence" not in scopes


def test_empty_input_manifest_is_error_scope():
    results = evaluate_guardrails(_rationale(), input_manifest=[])
    assert any(
        item.rule_id == "input.manifest.v1"
        and item.result == GuardrailStatus.ERROR
        and item.scope == "input"
        for item in results
    )
    results = evaluate_guardrails(_rationale(summary="Patient TEST-00001 remains hypertensive."))
    assert any(item.rule_id == "phi_scan.v1" and item.result == GuardrailStatus.WARN for item in results)
