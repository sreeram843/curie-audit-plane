from dataclasses import dataclass
from datetime import UTC, datetime

from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.models.manifests import Finding, ModelManifest, StructuredRationale


@dataclass(frozen=True)
class StubResult:
    output: StructuredRationale
    manifest: ModelManifest
    request_digest: str
    response_digest: str


def stub_complete(
    context_digest: str,
    prompt_version: str = "clinical-summary.v1",
    model_id: str = "curie-stub-summary",
    evidence_ids: list[str] | None = None,
) -> StubResult:
    allowed = evidence_ids or []
    blood_pressure_ref = next(
        (item for item in allowed if item.startswith("obs-bp-")),
        "obs-bp-TEST-00001",
    )
    medication_ref = next(
        (item for item in allowed if item.startswith("med-lisinopril-")),
        "med-lisinopril-TEST-00001",
    )
    hypertension_ref = next(
        (item for item in allowed if item.startswith("htn-bp-target.")),
        "htn-bp-target.v1",
    )
    summary = f"Encounter summary ({prompt_version}) for context {context_digest[:12]}."
    if prompt_version.endswith("v2"):
        summary = f"Updated template: {summary}"
    output = StructuredRationale(
        summary=summary,
        findings=[
            Finding(
                text="Office blood pressure 148/92 mmHg",
                evidence_refs=[blood_pressure_ref, hypertension_ref],
            ),
            Finding(
                text="Active lisinopril 10 mg",
                evidence_refs=[medication_ref],
            ),
        ],
        evidence_references=[
            blood_pressure_ref,
            medication_ref,
            hypertension_ref,
        ],
        uncertainty="Single office visit; home readings unavailable.",
        assumptions=["The synthetic bundle is the complete available context."],
        missing_data=["Home blood pressure series", "Medication adherence"],
        follow_up_questions=["Has the patient taken lisinopril this morning?"],
    )
    now = datetime.now(UTC)
    manifest = ModelManifest(
        model_id=model_id,
        provider_id="curie-stub",
        endpoint="stub://local",
        model_version="stub-1.0.0",
        prompt_version=prompt_version,
        decoding_params={"temperature": 0, "seed": 0},
        tool_policy="knowledge.lookup",
        runtime="deterministic-stub",
        seed=0,
        requested_at=now,
        responded_at=now,
    )
    return StubResult(
        output=output,
        manifest=manifest,
        request_digest=sha256_hex(context_digest.encode("utf-8")),
        response_digest=sha256_hex(canonicalize(output.model_dump(mode="json"))),
    )
