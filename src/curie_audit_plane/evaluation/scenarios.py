from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from curie_audit_plane.adapters.completion import (
    Completer,
    CompletionRequest,
    CompletionResult,
    complete_stub,
)
from curie_audit_plane.evaluation.encounter_slice import slice_first_encounter
from curie_audit_plane.evaluation.fields import audit_reconstruction_completeness
from curie_audit_plane.fhir.loader import iter_resources, load_bundle
from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.models.enums import EventType, GuardrailStatus, HumanActionStatus
from curie_audit_plane.models.manifests import Finding, StructuredRationale
from curie_audit_plane.pipeline import DEFAULT_FIXTURE, REPO_ROOT, Pipeline

_SYNTHEA_SYSTEM = "https://github.com/synthetichealth/synthea"
_SYNTHEA_MANIFEST_PATH = REPO_ROOT / "fixtures/synthea/approved-manifest.json"

_MODIFIED = StructuredRationale(
    summary="Reviewer-shortened synthetic summary for MODIFY evaluation.",
    findings=[Finding(text="Hypertension", evidence_refs=["cond-htn-TEST-00001"])],
    evidence_references=["cond-htn-TEST-00001"],
    uncertainty="Reviewer edited the model output.",
    assumptions=["Bounded synthetic context remains the source of truth."],
    missing_data=["None added by the reviewer."],
    follow_up_questions=["Confirm the reviewer edit is recorded."],
)

_WARN_OUTPUT = StructuredRationale(
    summary="Synthetic phi-scan trigger TEST-00001 with cited evidence.",
    findings=[Finding(text="Office blood pressure 148/92 mmHg", evidence_refs=["obs-bp-TEST-00001"])],
    evidence_references=["obs-bp-TEST-00001"],
    uncertainty="Single office visit; home readings unavailable.",
    assumptions=["The synthetic bundle is the complete available context."],
    missing_data=["Home blood pressure series"],
    follow_up_questions=["Has the patient taken lisinopril this morning?"],
)


def _is_synthea_bundle(path: Path) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return False
    if payload.get("resourceType") != "Bundle":
        return False
    for resource in iter_resources(payload):
        if resource.get("resourceType") != "Patient":
            continue
        for identifier in resource.get("identifier") or []:
            if isinstance(identifier, dict) and identifier.get("system") == _SYNTHEA_SYSTEM:
                return True
    return False


def synthea_manifest() -> dict[str, object]:
    return json.loads(_SYNTHEA_MANIFEST_PATH.read_text(encoding="utf-8"))


def approved_synthea_roots() -> list[Path]:
    return [(REPO_ROOT / str(item)).resolve() for item in synthea_manifest().get("approved_roots") or []]


def _is_under_approved_root(path: Path) -> bool:
    resolved = path.resolve()
    for root in approved_synthea_roots():
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _collect_synthea(candidate: Path) -> list[Path]:
    discovered: list[Path] = []
    if (
        candidate.is_file()
        and candidate.suffix == ".json"
        and "Information" not in candidate.name
        and _is_synthea_bundle(candidate)
    ):
        discovered.append(candidate)
    elif candidate.is_dir():
        discovered.extend(
            path
            for path in sorted(candidate.glob("*.json"))
            if "Information" not in path.name and _is_synthea_bundle(path)
        )
    return discovered


def discover_synthea_bundles() -> list[Path]:
    configured = os.environ.get("CURIE_SYNTHEA_BUNDLE") or os.environ.get("CURIE_SYNTHEA_DIR")
    if configured:
        candidate = Path(configured)
        if _is_under_approved_root(candidate):
            return _collect_synthea(candidate)
        return []
    discovered: list[Path] = []
    for root in approved_synthea_roots():
        discovered.extend(_collect_synthea(root))
        if discovered:
            return discovered
    return []


def _with_output(_inner: Completer, output: StructuredRationale) -> Completer:
    def completer(request: CompletionRequest) -> CompletionResult:
        # Inject controlled structured output without calling the configured
        # provider. Live models must not be required to emit a trigger phrase.
        result = complete_stub(request)
        payload = canonicalize(output.model_dump(mode="json"))
        return CompletionResult(
            output=output,
            manifest=result.manifest,
            request_digest=result.request_digest,
            response_digest=sha256_hex(payload),
            token_usage=result.token_usage,
        )

    return completer


def _boom(_request: CompletionRequest) -> CompletionResult:
    raise RuntimeError("scenario provider failure")


def _observation(
    *,
    name: str,
    result,
    human_action: str | None,
    forced_guardrail: str | None,
    notes: str = "",
    waiting_status: str | None = None,
    replay_result: str | None = None,
    access_event_count: int | None = None,
    source_evidence_references: list[str] | None = None,
    final_evidence_references: list[str] | None = None,
) -> dict[str, object]:
    arc, missing = audit_reconstruction_completeness(result)
    guardrail_rule_ids = [
        str(event.payload_metadata["rule_id"])
        for event in result.events
        if event.event_type == EventType.GUARDRAIL_COMPLETED
        and event.payload_metadata.get("rule_id")
    ]
    guardrail_results = {
        str(event.payload_metadata["rule_id"]): str(event.payload_metadata["result"])
        for event in result.events
        if event.event_type == EventType.GUARDRAIL_COMPLETED
        and event.payload_metadata.get("rule_id")
        and event.payload_metadata.get("result")
    }
    model_event = next(
        (event for event in result.events if event.event_type == EventType.MODEL_REQUESTED),
        None,
    )
    human_event = next(
        (event for event in result.events if event.event_type == EventType.HUMAN_ACTION_RECORDED),
        None,
    )
    output_event = next(
        (
            event
            for event in result.events
            if event.event_type == EventType.STRUCTURED_OUTPUT_VALIDATED
        ),
        None,
    )
    return {
        "name": name,
        "transaction_id": result.transaction.transaction_id,
        "transaction_status": result.transaction.status.value,
        "human_action": human_action or result.transaction.human_action.value,
        "forced_guardrail": forced_guardrail,
        "subject_ref": result.transaction.subject_ref,
        "verification_status": result.verification.status.value,
        "arc": arc,
        "missing_fields": missing,
        "event_count": len(result.events),
        "notes": notes,
        "waiting_status": waiting_status,
        "override_policy_version": (
            human_event.payload_metadata.get("override_policy_version")
            if human_event
            else None
        ),
        "guardrail_rule_ids": guardrail_rule_ids,
        "guardrail_results": guardrail_results,
        "runtime": model_event.payload_metadata.get("runtime") if model_event else None,
        "replay_result": replay_result,
        "access_event_count": access_event_count,
        "source_output_digest": output_event.payload_digest if output_event else None,
        "final_output_digest": (
            human_event.payload_metadata.get("final_output_digest") if human_event else None
        ),
        "source_evidence_references": source_evidence_references,
        "final_evidence_references": final_evidence_references,
    }


def run_scenario_matrix(pipeline: Pipeline) -> dict[str, object]:
    original = pipeline.fixture_path
    original_completer = pipeline.completer
    scenarios: list[dict[str, object]] = []
    try:
        pipeline.fixture_path = original or DEFAULT_FIXTURE
        scenarios.append(
            _observation(
                name="accept",
                result=pipeline.run_transaction(
                    human_action=HumanActionStatus.ACCEPT,
                    actor="reviewer@curie.local",
                ),
                human_action=HumanActionStatus.ACCEPT.value,
                forced_guardrail=None,
            )
        )
        scenarios.append(
            _observation(
                name="modify",
                result=pipeline.run_transaction(
                    human_action=HumanActionStatus.MODIFY,
                    actor="reviewer@curie.local",
                    modified_output=_MODIFIED,
                    comment="MODIFY evaluation arm",
                ),
                human_action=HumanActionStatus.MODIFY.value,
                forced_guardrail=None,
            )
        )
        scenarios.append(
            _observation(
                name="reject",
                result=pipeline.run_transaction(
                    human_action=HumanActionStatus.REJECT,
                    actor="reviewer@curie.local",
                    comment="REJECT evaluation arm",
                ),
                human_action=HumanActionStatus.REJECT.value,
                forced_guardrail=None,
            )
        )
        scenarios.append(
            _observation(
                name="guardrail_warn",
                result=pipeline.run_transaction(
                    human_action=HumanActionStatus.ACCEPT,
                    actor="reviewer@curie.local",
                    force_guardrail=GuardrailStatus.WARN,
                ),
                human_action=HumanActionStatus.ACCEPT.value,
                forced_guardrail=GuardrailStatus.WARN.value,
            )
        )
        scenarios.append(
            _observation(
                name="guardrail_block",
                result=pipeline.run_transaction(
                    force_guardrail=GuardrailStatus.BLOCK,
                    actor="reviewer@curie.local",
                ),
                human_action=HumanActionStatus.PENDING.value,
                forced_guardrail=GuardrailStatus.BLOCK.value,
                notes="Blocked before human ACCEPT; incomplete required events are expected.",
            )
        )
        synthea_bundles = discover_synthea_bundles()
        if not synthea_bundles:
            for name in ("synthea_sliced", "synthea_sliced_second"):
                scenarios.append(
                    {
                        "name": name,
                        "status": "NOT_AVAILABLE",
                        "notes": (
                            "No eligible Synthea patient bundle under an approved root "
                            "in fixtures/synthea/approved-manifest.json."
                        ),
                    }
                )
        else:
            for index, name in enumerate(("synthea_sliced", "synthea_sliced_second")):
                if index >= len(synthea_bundles):
                    scenarios.append(
                        {
                            "name": name,
                            "status": "NOT_AVAILABLE",
                            "notes": "A second patient Synthea bundle was not available.",
                        }
                    )
                    continue
                synthea = synthea_bundles[index]
                sliced = slice_first_encounter(load_bundle(synthea))
                with NamedTemporaryFile(
                    "w", suffix=".json", delete=False, encoding="utf-8"
                ) as handle:
                    json.dump(sliced, handle)
                    sliced_path = Path(handle.name)
                try:
                    pipeline.fixture_path = sliced_path
                    scenarios.append(
                        _observation(
                            name=name,
                            result=pipeline.run_transaction(
                                human_action=HumanActionStatus.ACCEPT,
                                actor="reviewer@curie.local",
                            ),
                            human_action=HumanActionStatus.ACCEPT.value,
                            forced_guardrail=None,
                            notes=(
                                f"Sliced first encounter from approved Synthea bundle "
                                f"{index + 1} of {len(synthea_bundles)} "
                                f"(source digest {sha256_hex(synthea.read_bytes())[:12]}, "
                                f"license {synthea_manifest().get('license')}, "
                                f"source {synthea_manifest().get('source')}); "
                                "not copied into this repository."
                            ),
                        )
                    )
                finally:
                    sliced_path.unlink(missing_ok=True)

        pipeline.fixture_path = original or DEFAULT_FIXTURE
        waiting = pipeline.run_transaction(actor="reviewer@curie.local")
        completed = pipeline.record_human_action(
            waiting.transaction.transaction_id,
            action=HumanActionStatus.ACCEPT,
            actor="reviewer@curie.local",
        )
        scenarios.append(
            _observation(
                name="two_step_accept",
                result=completed,
                human_action=HumanActionStatus.ACCEPT.value,
                forced_guardrail=None,
                waiting_status=waiting.transaction.status.value,
            )
        )

        scenarios.append(
            _observation(
                name="block_override_accept",
                result=pipeline.run_transaction(
                    human_action=HumanActionStatus.ACCEPT,
                    actor="reviewer@curie.local",
                    force_guardrail=GuardrailStatus.BLOCK,
                    override_policy_version="override.v1",
                ),
                human_action=HumanActionStatus.ACCEPT.value,
                forced_guardrail=GuardrailStatus.BLOCK.value,
            )
        )

        try:
            pipeline.completer = _with_output(original_completer, _WARN_OUTPUT)
            scenarios.append(
                _observation(
                    name="natural_guardrail_warn",
                    result=pipeline.run_transaction(
                        human_action=HumanActionStatus.ACCEPT,
                        actor="reviewer@curie.local",
                    ),
                    human_action=HumanActionStatus.ACCEPT.value,
                    forced_guardrail=None,
                )
            )
        finally:
            pipeline.completer = original_completer

        natural_block_output = StructuredRationale(
            summary="Unsupported claim in synthetic output.",
            findings=[Finding(text="Unsupported claim", evidence_refs=[])],
            evidence_references=[],
            uncertainty="The claim could not be supported.",
            assumptions=[],
            missing_data=[],
            follow_up_questions=[],
        )
        original_completer = pipeline.completer
        try:
            pipeline.completer = _with_output(original_completer, natural_block_output)
            scenarios.append(
                _observation(
                    name="natural_guardrail_block",
                    result=pipeline.run_transaction(actor="reviewer@curie.local"),
                    human_action=HumanActionStatus.PENDING.value,
                    forced_guardrail=None,
                )
            )
        finally:
            pipeline.completer = original_completer

        original_completer = pipeline.completer
        try:
            pipeline.completer = _boom
            scenarios.append(
                _observation(
                    name="provider_failure",
                    result=pipeline.run_transaction(actor="reviewer@curie.local"),
                    human_action=HumanActionStatus.PENDING.value,
                    forced_guardrail=None,
                )
            )
        finally:
            pipeline.completer = original_completer

        sparse_bundle = {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": "2026-01-01T00:00:00Z",
            "entry": [
                {"resource": {"resourceType": "Patient", "id": "sparse-1"}},
                {
                    "resource": {
                        "resourceType": "Encounter",
                        "id": "enc-sparse-1",
                        "status": "finished",
                        "class": {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": "AMB",
                        },
                        "subject": {"reference": "Patient/sparse-1"},
                    }
                },
            ],
        }
        with NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(sparse_bundle, handle)
            sparse_path = Path(handle.name)
        try:
            pipeline.fixture_path = sparse_path
            scenarios.append(
                _observation(
                    name="sparse_encounter",
                    result=pipeline.run_transaction(
                        human_action=HumanActionStatus.ACCEPT,
                        actor="reviewer@curie.local",
                    ),
                    human_action=HumanActionStatus.ACCEPT.value,
                    forced_guardrail=None,
                )
            )
        finally:
            sparse_path.unlink(missing_ok=True)

        pipeline.fixture_path = original or DEFAULT_FIXTURE
        accepted = pipeline.run_transaction(
            human_action=HumanActionStatus.ACCEPT,
            actor="reviewer@curie.local",
        )
        modified = pipeline.run_transaction(
            human_action=HumanActionStatus.MODIFY,
            actor="reviewer@curie.local",
            modified_output=_MODIFIED,
            comment="MODIFY evidence evaluation arm",
        )
        scenarios.append(
            _observation(
                name="modify_evidence",
                result=modified,
                human_action=HumanActionStatus.MODIFY.value,
                forced_guardrail=None,
                source_evidence_references=list(accepted.output.evidence_references)
                if accepted.output
                else [],
                final_evidence_references=list(_MODIFIED.evidence_references),
            )
        )

        replay_source = pipeline.run_transaction(
            human_action=HumanActionStatus.ACCEPT,
            actor="reviewer@curie.local",
        )
        replay = pipeline.replay(
            replay_source.transaction.transaction_id,
            prompt_version="clinical-summary.v2",
        )
        sealed_replay = pipeline.load_result(replay_source.transaction.transaction_id)
        scenarios.append(
            _observation(
                name="replay_substitution",
                result=sealed_replay,
                human_action=HumanActionStatus.ACCEPT.value,
                forced_guardrail=None,
                replay_result=replay.result,
            )
        )

        access_source = pipeline.run_transaction(
            human_action=HumanActionStatus.ACCEPT,
            actor="reviewer@curie.local",
        )
        pipeline.record_access(
            access_source.transaction.transaction_id,
            actor="investigator@curie.local",
            role="investigator",
            action="export",
            endpoint="export",
        )
        pipeline.replay(access_source.transaction.transaction_id)
        sealed_access = pipeline.load_result(access_source.transaction.transaction_id)
        scenarios.append(
            _observation(
                name="access_audit",
                result=sealed_access,
                human_action=HumanActionStatus.ACCEPT.value,
                forced_guardrail=None,
                access_event_count=len(
                    pipeline.services.audit.list_access_events(
                        access_source.transaction.transaction_id
                    )
                ),
            )
        )
    finally:
        pipeline.fixture_path = original
        pipeline.completer = original_completer
    return {"scenarios": scenarios}
