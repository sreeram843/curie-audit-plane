from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from curie_audit_plane.adapters.completion import Completer, CompletionRequest, complete_stub
from curie_audit_plane.adapters.openai_compatible import complete_openai_compatible
from curie_audit_plane.adapters.retrieval import lookup_tool, retrieve_evidence
from curie_audit_plane.config import settings
from curie_audit_plane.fhir.context import apply_transformations, build_context
from curie_audit_plane.fhir.loader import build_input_manifest, iter_resources, load_bundle
from curie_audit_plane.guardrails.engine import evaluate_guardrails
from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import GENESIS_HASH, hash_event, sha256_hex
from curie_audit_plane.integrity.merkle import merkle_proof, merkle_root
from curie_audit_plane.integrity.signing import sign_hex
from curie_audit_plane.integrity.verifier import verify_transaction
from curie_audit_plane.models.enums import (
    TERMINAL_HUMAN_ACTIONS,
    EventStatus,
    EventType,
    GuardrailStatus,
    HumanActionStatus,
    TransactionStatus,
    VerificationStatus,
)
from curie_audit_plane.models.event import AuditEventRecord
from curie_audit_plane.models.manifests import IntegrityBatch, StructuredRationale
from curie_audit_plane.models.report import (
    ReplayClassification,
    TransactionOverview,
    VerificationReport,
)
from curie_audit_plane.privacy import (
    opaque_identifier,
    sanitize_comment,
    sanitize_override_policy_version,
    sanitize_prompt_version,
    sanitize_purpose,
)
from curie_audit_plane.replay import classify_replay_outputs, finalize_replay_result
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURE = REPO_ROOT / "fixtures/fhir/synthetic-encounter-bundle.json"
DEFAULT_CORPUS = REPO_ROOT / "fixtures/corpus/clinical-knowledge.v1.json"


@dataclass
class PipelineServices:
    audit: AuditStore
    content: ProtectedContentStore
    private_key: bytes
    public_key: bytes
    key_id: str = "cap-dev-key"


@dataclass
class TransactionState:
    transaction_id: str
    purpose: str
    subject_ref: str
    status: TransactionStatus
    human_action: HumanActionStatus
    started_at: datetime
    ended_at: datetime | None = None
    verification_status: VerificationStatus = VerificationStatus.NOT_RUN


@dataclass
class TransactionResult:
    transaction: TransactionState
    events: list[AuditEventRecord]
    verification: VerificationReport
    overview: TransactionOverview
    batch: IntegrityBatch | None = None
    output: StructuredRationale | None = None


@dataclass
class _RunContext:
    transaction_id: str
    sequence: int = 0
    previous_hash: str = GENESIS_HASH
    events: list[AuditEventRecord] = field(default_factory=list)


class Pipeline:
    def __init__(
        self,
        services: PipelineServices,
        fixture_path: Path | None = None,
        corpus_path: Path | None = None,
        completer: Completer | None = None,
    ) -> None:
        self.services = services
        self.fixture_path = fixture_path or DEFAULT_FIXTURE
        self.corpus_path = corpus_path or DEFAULT_CORPUS
        self.completer = completer or complete_stub

    def close(self) -> None:
        self.services.audit.close()

    def __enter__(self) -> Pipeline:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def run_unrecorded_workflow(
        self,
        *,
        prompt_version: str = "clinical-summary.v1",
        model_id: str = "curie-stub-summary",
        log_path: Path | None = None,
        human_action: HumanActionStatus = HumanActionStatus.ACCEPT,
        actor: str = "reviewer@curie.local",
        override_policy_version: str | None = None,
    ) -> dict[str, object]:
        if human_action not in TERMINAL_HUMAN_ACTIONS:
            raise ValueError("PENDING is a review state, not a terminal human disposition")
        bundle = load_bundle(self.fixture_path)
        manifest = build_input_manifest(bundle, self.services.content)
        transforms = apply_transformations(bundle, self.services.content)
        context = build_context(bundle, self.services.content)
        evidence = retrieve_evidence(bundle, self.corpus_path, self.services.content)
        if evidence and evidence[0].chunk_id:
            lookup_tool(evidence[0].chunk_id, self.corpus_path, self.services.content)
        context_payload = json.loads(self.services.content.get(context.content_ref).decode("utf-8"))
        completion = self.completer(
            self._completion_request(
                context.digest, context_payload, evidence, prompt_version, model_id
            )
        )
        guardrails = evaluate_guardrails(
            completion.output,
            input_manifest=manifest,
            context_ref=context.content_ref,
            context_digest=context.digest,
            evidence=evidence,
        )
        records = [
            {"stage": "load", "status": "ok"},
            {"stage": "transform", "count": len(transforms)},
            {"stage": "context", "digest": context.digest},
            {"stage": "retrieve", "count": len(evidence)},
            {"stage": "complete", "model_id": completion.manifest.model_id},
            {"stage": "guardrail", "count": len(guardrails)},
        ]
        blocked = any(item.result == GuardrailStatus.BLOCK for item in guardrails)
        if not (blocked and human_action == HumanActionStatus.ACCEPT and not override_policy_version):
            category = "policy_override" if override_policy_version else {
                HumanActionStatus.ACCEPT: "accept_as_recorded",
                HumanActionStatus.MODIFY: "modify_for_accuracy",
                HumanActionStatus.REJECT: "reject_insufficient_evidence",
            }.get(human_action, "unspecified")
            sanitize_comment("", category=category)
            final_digest = sha256_hex(canonicalize(completion.output.model_dump(mode="json")))
            records.append(
                {
                    "stage": "review",
                    "action": human_action.value,
                    "actor": actor,
                    "final_output_digest": final_digest,
                }
            )
        payload = "\n".join(json.dumps(item) for item in records) + "\n"
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(payload, encoding="utf-8")
        return {
            "output": completion.output,
            "guardrails": guardrails,
            "log_bytes": len(payload.encode("utf-8")),
            "records": records,
        }

    def run_transaction(
        self,
        *,
        purpose: str = "synthetic-encounter-summary",
        human_action: HumanActionStatus | None = None,
        actor: str = "reviewer@curie.local",
        role: str = "clinical-reviewer",
        comment: str = "",
        modified_output: StructuredRationale | None = None,
        force_guardrail: GuardrailStatus | None = None,
        override_policy_version: str | None = None,
        prompt_version: str = "clinical-summary.v1",
        model_id: str = "curie-stub-summary",
    ) -> TransactionResult:
        if human_action is not None and human_action not in TERMINAL_HUMAN_ACTIONS:
            raise ValueError("PENDING is a review state, not a terminal human disposition")
        purpose = sanitize_purpose(purpose)
        prompt_version = sanitize_prompt_version(prompt_version)
        override_policy_version = sanitize_override_policy_version(override_policy_version)
        transaction_id = str(uuid4())
        started_at = datetime.now(UTC)
        ctx = _RunContext(transaction_id=transaction_id)
        subject_ref = opaque_identifier("Patient/UNKNOWN")
        try:
            bundle = load_bundle(self.fixture_path)
            patient = next(
                (
                    resource
                    for resource in iter_resources(bundle)
                    if resource.get("resourceType") == "Patient"
                ),
                None,
            )
            if patient is None or not patient.get("id"):
                raise ValueError("FHIR Bundle must include a Patient resource")
            raw_subject = f"Patient/{patient['id']}"
            subject_ref = opaque_identifier(raw_subject)
            self.services.audit.create_transaction(transaction_id, purpose, subject_ref)
            return self._run_transaction_inner(
                ctx,
                bundle=bundle,
                purpose=purpose,
                subject_ref=subject_ref,
                raw_subject=raw_subject,
                started_at=started_at,
                human_action=human_action,
                actor=actor,
                role=role,
                comment=comment,
                modified_output=modified_output,
                force_guardrail=force_guardrail,
                override_policy_version=override_policy_version,
                prompt_version=prompt_version,
                model_id=model_id,
            )
        except Exception as exc:
            try:
                self.services.audit.get_transaction(transaction_id)
            except KeyError:
                self.services.audit.create_transaction(transaction_id, purpose, subject_ref)
            return self._fail_transaction(ctx, purpose, subject_ref, started_at, exc)

    def _run_transaction_inner(
        self,
        ctx: _RunContext,
        *,
        bundle: dict[str, object],
        purpose: str,
        subject_ref: str,
        raw_subject: str,
        started_at: datetime,
        human_action: HumanActionStatus | None,
        actor: str,
        role: str,
        comment: str,
        modified_output: StructuredRationale | None,
        force_guardrail: GuardrailStatus | None,
        override_policy_version: str | None,
        prompt_version: str,
        model_id: str,
    ) -> TransactionResult:
        transaction_id = ctx.transaction_id
        manifest = build_input_manifest(bundle, self.services.content)
        identity = {
            "subject_raw": raw_subject,
            "subject_opaque": subject_ref,
            "resources": [
                {
                    "resource_type": item.resource_type,
                    "raw": item.resource_id,
                    "opaque": opaque_identifier(item.resource_id),
                }
                for item in manifest
            ],
        }
        identity_bytes = canonicalize(identity)
        identity_ref = self.services.content.put(identity_bytes, "application/json")
        opaque_ids = [item["opaque"] for item in identity["resources"]]
        self._emit(
            ctx,
            EventType.TRANSACTION_STARTED,
            {
                "purpose": purpose,
                "subject_ref": subject_ref,
                "identity_ref": identity_ref,
                "source_system": "curie-fhir-fixture",
            },
        )
        self.services.audit.set_status(transaction_id, TransactionStatus.RUNNING)

        self._emit(
            ctx,
            EventType.INPUT_MANIFEST_CREATED,
            {
                "item_count": len(manifest),
                "resource_ids": opaque_ids,
                "resources": [
                    {"resource_type": item.resource_type, "resource_id": opaque_identifier(item.resource_id)}
                    for item in manifest
                ],
                "source_system": "curie-fhir-fixture",
            },
            canonicalize([item.model_dump(mode="json") for item in manifest]),
        )

        transforms = apply_transformations(bundle, self.services.content)
        for record in transforms:
            self._emit(
                ctx,
                EventType.TRANSFORMATION_APPLIED,
                {
                    "operation_id": record.operation_id,
                    "operation_name": record.operation_name,
                    "code_version": record.code_version,
                    "parameters_digest": record.parameters_digest,
                    "input_refs": record.input_refs,
                    "output_ref": record.output_ref,
                    "output_digest": record.output_digest,
                },
                payload_ref=record.output_ref,
                payload_digest=record.output_digest,
            )

        context = build_context(bundle, self.services.content)
        self._emit(
            ctx,
            EventType.CONTEXT_MANIFEST_CREATED,
            {"serialization": context.serialization, "source": "curie-fhir-fixture"},
            payload_ref=context.content_ref,
            payload_digest=context.digest,
        )

        evidence = retrieve_evidence(bundle, self.corpus_path, self.services.content)
        self._emit(
            ctx,
            EventType.RETRIEVAL_COMPLETED,
            {
                "corpus_id": "clinical-knowledge",
                "corpus_version": "clinical-knowledge.v1",
                "count": len(evidence),
                "chunk_ids": [item.chunk_id for item in evidence],
            },
            canonicalize([item.model_dump(mode="json") for item in evidence]),
        )

        if evidence and evidence[0].chunk_id:
            tool = lookup_tool(evidence[0].chunk_id, self.corpus_path, self.services.content)
            self._emit(
                ctx,
                EventType.TOOL_CALLED,
                {
                    "tool_id": tool.tool_id,
                    "tool_version": tool.tool_version,
                    "sanitized_arguments": tool.sanitized_arguments,
                    "result_digest": tool.result_digest,
                },
                payload_ref=tool.result_ref,
                payload_digest=tool.result_digest,
            )
            self._emit(
                ctx,
                EventType.TOOL_COMPLETED,
                {"tool_id": tool.tool_id, "status": tool.status.value},
                payload_ref=tool.result_ref,
                payload_digest=tool.result_digest,
            )

        context_payload = json.loads(self.services.content.get(context.content_ref).decode("utf-8"))
        completion = self.completer(self._completion_request(context.digest, context_payload, evidence, prompt_version, model_id))
        self._emit(
            ctx,
            EventType.MODEL_REQUESTED,
            {
                "model_id": completion.manifest.model_id,
                "provider_id": completion.manifest.provider_id,
                "endpoint": completion.manifest.endpoint,
                "model_version": completion.manifest.model_version,
                "prompt_version": completion.manifest.prompt_version,
                "decoding_params": completion.manifest.decoding_params,
                "tool_policy": completion.manifest.tool_policy,
                "runtime": completion.manifest.runtime,
                "request_digest": completion.request_digest,
            },
        )
        output_bytes = canonicalize(completion.output.model_dump(mode="json"))
        output_ref = self.services.content.put(output_bytes, "application/json")
        output_digest = self.services.content.digest_of(output_bytes)
        self._emit(
            ctx,
            EventType.MODEL_RESPONDED,
            {
                "status": "ok",
                "token_usage": completion.token_usage,
                "response_digest": completion.response_digest,
            },
            payload_ref=output_ref,
            payload_digest=output_digest,
        )
        self._emit(
            ctx,
            EventType.STRUCTURED_OUTPUT_VALIDATED,
            {
                "schema_version": "1.0.0",
                "finding_count": len(completion.output.findings),
                "evidence_count": len(completion.output.evidence_references),
            },
            payload_ref=output_ref,
            payload_digest=output_digest,
        )

        guardrails = evaluate_guardrails(
            completion.output,
            input_manifest=manifest,
            context_ref=context.content_ref,
            context_digest=context.digest,
            evidence=evidence,
        )
        if force_guardrail is not None:
            guardrails.append(
                evaluate_guardrails(completion.output)[1].model_copy(
                    update={
                        "rule_id": "forced.v1",
                        "result": force_guardrail,
                        "override_required": force_guardrail == GuardrailStatus.BLOCK,
                        "message": "forced guardrail status for tests",
                    }
                )
            )
        blocked = any(item.result == GuardrailStatus.BLOCK for item in guardrails)
        errored = any(item.result == GuardrailStatus.ERROR for item in guardrails)
        for item in guardrails:
            self._emit(
                ctx,
                EventType.GUARDRAIL_COMPLETED,
                {
                    "rule_id": item.rule_id,
                    "rule_version": item.rule_version,
                    "scope": item.scope,
                    "result": item.result.value,
                    "severity": item.severity,
                    "override_required": item.override_required,
                    "message": item.message,
                    "input_ref": item.input_ref,
                    "digest": item.digest,
                },
            )

        status = TransactionStatus.BLOCKED if blocked else TransactionStatus.WAITING_FOR_REVIEW
        self.services.audit.set_status(transaction_id, status)
        if errored and not blocked:
            return self._fail_transaction(
                ctx, purpose, subject_ref, started_at, ValueError("guardrail error")
            )
        if human_action is not None:
            return self._complete_review(
                ctx,
                output_ref=output_ref,
                output_digest=output_digest,
                human_action=human_action,
                actor=actor,
                role=role,
                comment=comment,
                modified_output=modified_output,
                override_policy_version=override_policy_version,
                blocked=blocked,
                started_at=started_at,
                purpose=purpose,
                subject_ref=subject_ref,
                output=completion.output,
            )
        verification = self._verify(ctx.events, None, ctx.transaction_id)
        return self._result(
            ctx,
            status=status,
            human_status=HumanActionStatus.PENDING,
            started_at=started_at,
            ended_at=None,
            purpose=purpose,
            subject_ref=subject_ref,
            verification=verification,
            batch=None,
            output=completion.output,
        )

    def record_human_action(
        self,
        transaction_id: str,
        *,
        action: HumanActionStatus,
        actor: str,
        role: str = "clinical-reviewer",
        comment: str = "",
        modified_output: StructuredRationale | None = None,
        override_policy_version: str | None = None,
    ) -> TransactionResult:
        if action not in TERMINAL_HUMAN_ACTIONS:
            raise ValueError("PENDING is a review state, not a terminal human disposition")
        override_policy_version = sanitize_override_policy_version(override_policy_version)
        events = self.services.audit.list_events(transaction_id)
        if not events:
            raise KeyError(transaction_id)
        if any(event.event_type == EventType.HUMAN_ACTION_RECORDED for event in events):
            raise ValueError("transaction already has a human disposition")
        output_event = next(
            event for event in events if event.event_type == EventType.STRUCTURED_OUTPUT_VALIDATED
        )
        blocked = any(
            event.event_type == EventType.GUARDRAIL_COMPLETED
            and event.payload_metadata.get("result") == GuardrailStatus.BLOCK.value
            for event in events
        )
        row = self.services.audit.get_transaction(transaction_id)
        ctx = _RunContext(
            transaction_id=transaction_id,
            sequence=len(events),
            previous_hash=events[-1].event_hash,
            events=list(events),
        )
        output = StructuredRationale.model_validate_json(
            self.services.content.get(output_event.payload_ref or "")
        )
        return self._complete_review(
            ctx,
            output_ref=output_event.payload_ref or "",
            output_digest=output_event.payload_digest or "",
            human_action=action,
            actor=actor,
            role=role,
            comment=comment,
            modified_output=modified_output,
            override_policy_version=override_policy_version,
            blocked=blocked,
            started_at=datetime.fromisoformat(row["created_at"] or datetime.now(UTC).isoformat()),
            purpose=row["purpose"] or "synthetic-encounter-summary",
            subject_ref=row["subject_ref"] or opaque_identifier("Patient/UNKNOWN"),
            output=output,
        )

    def load_result(self, transaction_id: str) -> TransactionResult:
        events = self.services.audit.list_events(transaction_id)
        row = self.services.audit.get_transaction(transaction_id)
        batch = self._batch_from_events(events)
        verification = self._verify(events, batch, transaction_id)
        human = next(
            (event for event in events if event.event_type == EventType.HUMAN_ACTION_RECORDED),
            None,
        )
        human_status = HumanActionStatus(
            str(human.payload_metadata.get("action")) if human else HumanActionStatus.PENDING.value
        )
        output_event = next(
            (event for event in events if event.event_type == EventType.STRUCTURED_OUTPUT_VALIDATED),
            None,
        )
        output = None
        if output_event and output_event.payload_ref:
            try:
                output = StructuredRationale.model_validate_json(
                    self.services.content.get(output_event.payload_ref)
                )
            except (FileNotFoundError, ValueError):
                output = None
        return self._result(
            _RunContext(transaction_id=transaction_id, sequence=len(events), events=events),
            status=TransactionStatus(row["status"] or TransactionStatus.RUNNING.value),
            human_status=human_status,
            started_at=datetime.fromisoformat(row["created_at"] or datetime.now(UTC).isoformat()),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            purpose=row["purpose"] or "",
            subject_ref=row["subject_ref"] or "",
            verification=verification,
            batch=batch,
            output=output,
        )

    def _complete_review(
        self,
        ctx: _RunContext,
        *,
        output_ref: str,
        output_digest: str,
        human_action: HumanActionStatus,
        actor: str,
        role: str,
        comment: str,
        modified_output: StructuredRationale | None,
        override_policy_version: str | None,
        blocked: bool,
        started_at: datetime,
        purpose: str,
        subject_ref: str,
        output: StructuredRationale | None,
    ) -> TransactionResult:
        if blocked and human_action == HumanActionStatus.ACCEPT and not override_policy_version:
            verification = self._verify(ctx.events, None, ctx.transaction_id)
            self.services.audit.set_status(ctx.transaction_id, TransactionStatus.BLOCKED)
            return self._result(
                ctx,
                status=TransactionStatus.BLOCKED,
                human_status=HumanActionStatus.PENDING,
                started_at=started_at,
                ended_at=None,
                purpose=purpose,
                subject_ref=subject_ref,
                verification=verification,
                batch=None,
                output=output,
            )
        final_ref = output_ref
        final_digest = output_digest
        if human_action == HumanActionStatus.MODIFY:
            if modified_output is None:
                raise ValueError("MODIFY requires modified_output")
            modified_bytes = canonicalize(modified_output.model_dump(mode="json"))
            final_ref = self.services.content.put(modified_bytes, "application/json")
            final_digest = self.services.content.digest_of(modified_bytes)
        category = "policy_override" if override_policy_version else {
            HumanActionStatus.ACCEPT: "accept_as_recorded",
            HumanActionStatus.MODIFY: "modify_for_accuracy",
            HumanActionStatus.REJECT: "reject_insufficient_evidence",
        }.get(human_action, "unspecified")
        sanitized = sanitize_comment(comment, category=category)
        if sanitized["comment_present"]:
            comment_bytes = canonicalize({"comment": comment})
            sanitized["comment_ref"] = self.services.content.put(comment_bytes, "text/plain")
        self._emit(
            ctx,
            EventType.HUMAN_ACTION_RECORDED,
            {
                "action": human_action.value,
                "actor": actor,
                "role": role,
                "source_output_id": output_ref,
                "final_output_digest": final_digest,
                "override_policy_version": override_policy_version,
                **sanitized,
            },
            payload_ref=final_ref,
            payload_digest=final_digest,
        )
        ended_at = datetime.now(UTC)
        self._emit(ctx, EventType.TRANSACTION_COMPLETED, {"human_action": human_action.value})
        batch = self._commit_proof(ctx)
        verification = self._verify(ctx.events, batch, ctx.transaction_id)
        status = TransactionStatus.COMPLETED
        if verification.status != VerificationStatus.VERIFIED:
            status = (
                TransactionStatus.TAMPERED
                if verification.status == VerificationStatus.TAMPERED
                else TransactionStatus.INCOMPLETE
            )
        self.services.audit.set_status(ctx.transaction_id, status, ended_at=ended_at)
        return self._result(
            ctx,
            status=status,
            human_status=human_action,
            started_at=started_at,
            ended_at=ended_at,
            purpose=purpose,
            subject_ref=subject_ref,
            verification=verification,
            batch=batch,
            output=output,
        )

    def _commit_proof(self, ctx: _RunContext) -> IntegrityBatch:
        completed = next(
            event for event in ctx.events if event.event_type == EventType.TRANSACTION_COMPLETED
        )
        root = completed.event_hash
        merkle = merkle_root([root])
        proof = merkle_proof([root], 0)
        batch = IntegrityBatch(
            batch_id=str(uuid4()),
            transaction_ids=[ctx.transaction_id],
            transaction_roots=[root],
            merkle_root=merkle,
            signature=sign_hex(merkle, self.services.private_key),
            key_id=self.services.key_id,
            signed_at=datetime.now(UTC),
            inclusion_index=0,
            inclusion_proof=proof.path,
        )
        self._emit(
            ctx,
            EventType.INTEGRITY_PROOF_COMMITTED,
            {
                "batch_id": batch.batch_id,
                "merkle_root": batch.merkle_root,
                "signature": batch.signature,
                "key_id": batch.key_id,
                "transaction_root": root,
                "transaction_ids": batch.transaction_ids,
                "transaction_roots": batch.transaction_roots,
                "inclusion_index": batch.inclusion_index,
                "inclusion_proof": batch.inclusion_proof,
            },
        )
        return batch

    def _batch_from_events(self, events: list[AuditEventRecord]) -> IntegrityBatch | None:
        proof_event = next(
            (event for event in events if event.event_type == EventType.INTEGRITY_PROOF_COMMITTED),
            None,
        )
        if proof_event is None:
            return None
        meta = proof_event.payload_metadata
        roots = meta.get("transaction_roots") or [str(meta.get("transaction_root") or "")]
        ids = meta.get("transaction_ids") or [proof_event.transaction_id]
        return IntegrityBatch(
            batch_id=str(meta.get("batch_id") or "unknown"),
            transaction_ids=[str(item) for item in ids],
            transaction_roots=[str(item) for item in roots],
            merkle_root=str(meta.get("merkle_root") or ""),
            signature=str(meta.get("signature") or ""),
            key_id=str(meta.get("key_id") or self.services.key_id),
            signed_at=proof_event.occurred_at,
            inclusion_index=int(meta.get("inclusion_index") or 0),
            inclusion_proof=[str(item) for item in (meta.get("inclusion_proof") or [])],
        )

    def _result(
        self,
        ctx: _RunContext,
        *,
        status: TransactionStatus,
        human_status: HumanActionStatus,
        started_at: datetime,
        ended_at: datetime | None,
        purpose: str,
        subject_ref: str,
        verification: VerificationReport,
        batch: IntegrityBatch | None,
        output: StructuredRationale | None,
    ) -> TransactionResult:
        failed = [event.event_id for event in ctx.events if event.status == EventStatus.FAILED]
        overview = TransactionOverview(
            transaction_id=ctx.transaction_id,
            purpose=purpose,
            subject_ref=subject_ref,
            status=status,
            verification_status=verification.status,
            human_action=human_status,
            started_at=started_at,
            ended_at=ended_at,
            event_count=len(ctx.events),
            missing_event_count=len(verification.missing_events),
            failed_event_count=len(failed),
        )
        return TransactionResult(
            transaction=TransactionState(
                transaction_id=ctx.transaction_id,
                purpose=purpose,
                subject_ref=subject_ref,
                status=status,
                human_action=human_status,
                started_at=started_at,
                ended_at=ended_at,
                verification_status=verification.status,
            ),
            events=ctx.events,
            verification=verification,
            overview=overview,
            batch=batch,
            output=output,
        )

    def replay(
        self,
        transaction_id: str,
        *,
        actor: str = "investigator@curie.local",
        role: str = "investigator",
        prompt_version: str | None = None,
        model_id: str | None = None,
    ) -> ReplayClassification:
        events = self.services.audit.list_events(transaction_id)
        context_event = next(
            event for event in events if event.event_type == EventType.CONTEXT_MANIFEST_CREATED
        )
        output_event = next(
            event for event in events if event.event_type == EventType.STRUCTURED_OUTPUT_VALIDATED
        )
        model_event = next(event for event in events if event.event_type == EventType.MODEL_REQUESTED)
        retrieval_event = next(
            (event for event in events if event.event_type == EventType.RETRIEVAL_COMPLETED),
            None,
        )
        if prompt_version is None:
            prompt_version = str(
                model_event.payload_metadata.get("prompt_version") or "clinical-summary.v1"
            )
        if model_id is None:
            model_id = str(model_event.payload_metadata.get("model_id") or "curie-stub-summary")
        decoding_params = model_event.payload_metadata.get("decoding_params")
        tool_policy = model_event.payload_metadata.get("tool_policy")
        runtime = str(model_event.payload_metadata.get("runtime") or "")
        endpoint = str(model_event.payload_metadata.get("endpoint") or "")
        corpus_version = (
            retrieval_event.payload_metadata.get("corpus_version") if retrieval_event else None
        )
        digest = context_event.payload_digest or ""
        context_payload: object = []
        if context_event.payload_ref:
            context_payload = json.loads(self.services.content.get(context_event.payload_ref).decode("utf-8"))
        evidence_ids = []
        if retrieval_event:
            evidence_ids = [str(item) for item in retrieval_event.payload_metadata.get("chunk_ids") or [] if item]
        original = StructuredRationale.model_validate_json(
            self.services.content.get(output_event.payload_ref or "")
        )
        original_digest = output_event.payload_digest or ""
        replay_ref = None
        replay_digest = ""
        classification, reasons = finalize_replay_result(
            runtime=runtime,
            endpoint=endpoint,
            classification="EXACT_MATCH",
            reasons=[],
        )
        if classification != "NOT_REPLAYABLE":
            completer = self._completer_for_replay(model_event)
            completion = completer(
                CompletionRequest(
                    context_digest=digest,
                    context=context_payload,
                    evidence_ids=evidence_ids,
                    prompt_version=prompt_version,
                    model_id=model_id,
                    decoding_params=decoding_params if isinstance(decoding_params, dict) else None,
                    tool_policy=str(tool_policy) if tool_policy else None,
                )
            )
            classification, reasons = classify_replay_outputs(original, completion.output)
            classification, reasons = finalize_replay_result(
                runtime=runtime,
                endpoint=endpoint,
                classification=classification,
                reasons=reasons,
            )
            replay_bytes = canonicalize(completion.output.model_dump(mode="json"))
            replay_ref = self.services.content.put(replay_bytes, "application/json")
            replay_digest = self.services.content.digest_of(replay_bytes)
        decoding = decoding_params if isinstance(decoding_params, dict) else {}
        extra = {
            "model_id": model_id,
            "model_version": model_event.payload_metadata.get("model_version"),
            "prompt_version": prompt_version,
            "decoding_params": decoding_params,
            "tool_policy": tool_policy,
            "runtime": runtime,
            "endpoint": endpoint,
            "seed": decoding.get("seed"),
            "temperature": decoding.get("temperature"),
            "top_p": decoding.get("top_p"),
            "response_format": decoding.get("response_format"),
            "corpus_version": corpus_version,
            "original_digest": original_digest,
            "replay_digest": replay_digest,
            "replay_content_ref": replay_ref,
            "reasons": reasons,
        }
        self.record_access(
            transaction_id,
            actor=actor,
            role=role,
            action="replay",
            endpoint="replay",
            result=classification,
            extra=extra,
            event_type=EventType.REPLAY_RECORDED,
            payload_ref=replay_ref,
            payload_digest=replay_digest or None,
        )
        original_payload = original.model_dump(mode="json")
        replay_payload = None
        if classification != "NOT_REPLAYABLE" and replay_ref:
            replay_payload = json.loads(self.services.content.get(replay_ref).decode("utf-8"))
        elif classification != "NOT_REPLAYABLE":
            replay_payload = original_payload
        human = next((event for event in events if event.event_type == EventType.HUMAN_ACTION_RECORDED), None)
        modified_payload = None
        modified_event_id = None
        if human and str(human.payload_metadata.get("action")) == "MODIFY" and human.payload_ref:
            if human.payload_ref != output_event.payload_ref:
                modified_payload = StructuredRationale.model_validate_json(
                    self.services.content.get(human.payload_ref)
                ).model_dump(mode="json")
                modified_event_id = human.event_id
        return ReplayClassification(
            result=classification,
            original_digest=original_digest,
            replay_digest=replay_digest,
            reasons=reasons,
            replay_content_ref=replay_ref,
            original_output=original_payload,
            modified_output=modified_payload,
            replay_output=replay_payload,
            original_event_id=output_event.event_id,
            modified_event_id=modified_event_id,
        )

    def record_access(
        self,
        transaction_id: str,
        *,
        actor: str,
        role: str,
        action: str,
        endpoint: str,
        result: str = "ok",
        extra: dict[str, object] | None = None,
        event_type: EventType | None = None,
        payload_ref: str | None = None,
        payload_digest: str | None = None,
    ) -> AuditEventRecord:
        with self.services.audit.locked():
            previous = self.services.audit.list_access_events(transaction_id)
            previous_hash = previous[-1].event_hash if previous else GENESIS_HASH
            metadata = {
                "actor": actor,
                "role": role,
                "action": action,
                "endpoint": endpoint,
                "transaction_id": transaction_id,
                "result": result,
            }
            if extra:
                metadata.update(extra)
            event = AuditEventRecord(
                event_id=str(uuid4()),
                transaction_id=transaction_id,
                sequence_number=len(previous),
                event_type=event_type
                or (EventType.EXPORT_RECORDED if action == "export" else EventType.UI_ACCESS_RECORDED),
                actor_service="audit-console",
                occurred_at=datetime.now(UTC),
                payload_metadata=metadata,
                payload_ref=payload_ref,
                payload_digest=payload_digest,
                previous_event_hash=previous_hash,
                event_hash="",
            )
            event = event.model_copy(update={"event_hash": hash_event(event.model_dump(mode="json"))})
            self.services.audit.append_access_event(event)
            return event

    def _fail_transaction(
        self,
        ctx: _RunContext,
        purpose: str,
        subject_ref: str,
        started_at: datetime,
        exc: Exception,
    ) -> TransactionResult:
        ended_at = datetime.now(UTC)
        error_code = type(exc).__name__
        self._emit(
            ctx,
            EventType.TRANSACTION_FAILED,
            {
                "error_code": error_code,
                "message": "",
            },
            status=EventStatus.FAILED,
        )
        self.services.audit.set_status(ctx.transaction_id, TransactionStatus.FAILED, ended_at=ended_at)
        verification = self._verify(ctx.events, None, ctx.transaction_id)
        return self._result(
            ctx,
            status=TransactionStatus.FAILED,
            human_status=HumanActionStatus.PENDING,
            started_at=started_at,
            ended_at=ended_at,
            purpose=purpose,
            subject_ref=subject_ref,
            verification=verification,
            batch=None,
            output=None,
        )

    def _completion_request(
        self,
        context_digest: str,
        context_payload: object,
        evidence: list,
        prompt_version: str,
        model_id: str,
    ) -> CompletionRequest:
        evidence_ids = [item.evidence_id for item in evidence]
        if isinstance(context_payload, list):
            evidence_ids.extend(
                str(resource.get("id"))
                for resource in context_payload
                if isinstance(resource, dict) and resource.get("id")
            )
        return CompletionRequest(
            context_digest=context_digest,
            context=context_payload,
            evidence_ids=sorted({item for item in evidence_ids if item}),
            prompt_version=prompt_version,
            model_id=model_id,
        )

    def _verify(
        self,
        events: list[AuditEventRecord],
        batch: IntegrityBatch | None,
        transaction_id: str,
    ) -> VerificationReport:
        return verify_transaction(
            events,
            batch,
            self.services.public_key,
            expected_key_id=self.services.key_id,
            transaction_id=transaction_id,
            content_store=self.services.content,
        )

    def _completer_for_replay(self, model_event: AuditEventRecord) -> Completer:
        runtime = str(model_event.payload_metadata.get("runtime") or "")
        if runtime == "deterministic-stub":
            return complete_stub
        if runtime == "openai-compatible":
            endpoint = str(model_event.payload_metadata.get("endpoint") or "")
            recorded_endpoint = endpoint

            def _complete(request: CompletionRequest):
                return complete_openai_compatible(
                    request,
                    base_url=recorded_endpoint,
                    model=request.model_id,
                    api_key=settings.llm_api_key,
                    timeout_seconds=settings.llm_timeout_seconds,
                )

            return _complete
        return self.completer

    def _emit(
        self,
        ctx: _RunContext,
        event_type: EventType,
        metadata: dict[str, object],
        payload: bytes | None = None,
        *,
        payload_ref: str | None = None,
        payload_digest: str | None = None,
        status: EventStatus = EventStatus.RECORDED,
    ) -> AuditEventRecord:
        if payload is not None:
            payload_ref = self.services.content.put(payload, "application/json")
            payload_digest = self.services.content.digest_of(payload)
        event = AuditEventRecord(
            event_id=str(uuid4()),
            transaction_id=ctx.transaction_id,
            sequence_number=ctx.sequence,
            event_type=event_type,
            actor_service="curie-audit-plane",
            occurred_at=datetime.now(UTC),
            status=status,
            payload_ref=payload_ref,
            payload_digest=payload_digest,
            payload_metadata=metadata,
            previous_event_hash=ctx.previous_hash,
            event_hash="",
        )
        digest = hash_event(event.model_dump(mode="json"))
        event = event.model_copy(update={"event_hash": digest})
        self.services.audit.append_event(event)
        ctx.events.append(event)
        ctx.previous_hash = digest
        ctx.sequence += 1
        return event
