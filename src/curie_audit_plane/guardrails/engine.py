import json
import re

from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.models.enums import GuardrailScope, GuardrailStatus
from curie_audit_plane.models.manifests import (
    EvidenceItem,
    GuardrailResult,
    InputManifestItem,
    StructuredRationale,
)

_MRN_RE = re.compile(r"TEST-\d{5}")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def _result(
    rule_id: str,
    scope: GuardrailScope,
    result: GuardrailStatus,
    message: str,
    *,
    severity: str | None = None,
    override_required: bool = False,
    input_ref: str | None = None,
    digest: str | None = None,
) -> GuardrailResult:
    if severity is None:
        severity = {
            GuardrailStatus.PASS: "info",
            GuardrailStatus.WARN: "medium",
            GuardrailStatus.BLOCK: "high",
            GuardrailStatus.ERROR: "high",
        }[result]
    return GuardrailResult(
        rule_id=rule_id,
        rule_version="1.0.0",
        scope=scope.value,
        result=result,
        severity=severity,
        message=message,
        override_required=override_required,
        input_ref=input_ref,
        digest=digest,
    )


def evaluate_guardrails(
    output: StructuredRationale,
    *,
    input_manifest: list[InputManifestItem] | None = None,
    context_ref: str | None = None,
    context_digest: str | None = None,
    evidence: list[EvidenceItem] | None = None,
) -> list[GuardrailResult]:
    results: list[GuardrailResult] = []
    blob = json.dumps(output.model_dump(mode="json"))
    output_digest = sha256_hex(blob.encode("utf-8"))

    if input_manifest is not None:
        if not input_manifest:
            results.append(
                _result(
                    "input.manifest.v1",
                    GuardrailScope.INPUT,
                    GuardrailStatus.ERROR,
                    "input manifest is empty",
                )
            )
        elif any(not item.digest or not item.resource_type for item in input_manifest):
            results.append(
                _result(
                    "input.manifest.v1",
                    GuardrailScope.INPUT,
                    GuardrailStatus.ERROR,
                    "input manifest missing resource type or digest",
                )
            )
        else:
            results.append(
                _result(
                    "input.manifest.v1",
                    GuardrailScope.INPUT,
                    GuardrailStatus.PASS,
                    "input manifest items have types and digests",
                    digest=input_manifest[0].digest,
                    input_ref=input_manifest[0].content_ref,
                )
            )

    if context_digest is not None or context_ref is not None:
        if not context_digest or not context_ref:
            results.append(
                _result(
                    "context.bound.v1",
                    GuardrailScope.CONTEXT,
                    GuardrailStatus.ERROR,
                    "context reference or digest missing",
                    input_ref=context_ref,
                    digest=context_digest,
                )
            )
        else:
            results.append(
                _result(
                    "context.bound.v1",
                    GuardrailScope.CONTEXT,
                    GuardrailStatus.PASS,
                    "bounded context digest present",
                    input_ref=context_ref,
                    digest=context_digest,
                )
            )

    if evidence is not None:
        if any(not item.digest for item in evidence):
            results.append(
                _result(
                    "evidence.digest.v1",
                    GuardrailScope.EVIDENCE,
                    GuardrailStatus.ERROR,
                    "evidence item missing digest",
                )
            )
        else:
            results.append(
                _result(
                    "evidence.digest.v1",
                    GuardrailScope.EVIDENCE,
                    GuardrailStatus.PASS,
                    "evidence items include digests",
                    digest=evidence[0].digest if evidence else None,
                    input_ref=evidence[0].source_ref if evidence else None,
                )
            )

    findings = output.findings
    cited_findings = sum(1 for finding in findings if finding.evidence_refs)
    if findings and cited_findings == 0 and not output.evidence_references:
        evidence_status = GuardrailStatus.BLOCK
        evidence_message = "findings exist without evidence citations"
        override_required = True
    elif findings and any(not finding.evidence_refs for finding in findings):
        evidence_status = GuardrailStatus.WARN
        evidence_message = "some findings lack evidence references"
        override_required = False
    else:
        evidence_status = GuardrailStatus.PASS
        evidence_message = "findings cite evidence"
        override_required = False

    uncertainty_status = GuardrailStatus.PASS if output.uncertainty.strip() else GuardrailStatus.WARN
    phi_status = (
        GuardrailStatus.WARN if _MRN_RE.search(blob) or _SSN_RE.search(blob) else GuardrailStatus.PASS
    )
    results.extend(
        [
            _result(
                "schema.v1",
                GuardrailScope.STRUCTURED_OUTPUT,
                GuardrailStatus.PASS,
                "structured rationale schema valid",
                digest=output_digest,
            ),
            _result(
                "evidence_refs.v1",
                GuardrailScope.STRUCTURED_OUTPUT,
                evidence_status,
                evidence_message,
                override_required=override_required,
                digest=output_digest,
            ),
            _result(
                "uncertainty.v1",
                GuardrailScope.STRUCTURED_OUTPUT,
                uncertainty_status,
                "uncertainty present" if uncertainty_status == GuardrailStatus.PASS else "uncertainty empty",
                severity="low",
                digest=output_digest,
            ),
            _result(
                "phi_scan.v1",
                GuardrailScope.STRUCTURED_OUTPUT,
                phi_status,
                "synthetic identifier pattern detected" if phi_status == GuardrailStatus.WARN else "no identifier pattern",
                digest=output_digest,
            ),
        ]
    )

    blocked = any(item.result == GuardrailStatus.BLOCK for item in results)
    results.append(
        _result(
            "policy.action.v1",
            GuardrailScope.POLICY_ACTION,
            GuardrailStatus.BLOCK if blocked else GuardrailStatus.PASS,
            "blocked output requires explicit override" if blocked else "no policy override required",
            override_required=blocked,
        )
    )
    return results
