from dataclasses import dataclass, field
from typing import Any, Protocol

from curie_audit_plane.adapters.llm_stub import stub_complete
from curie_audit_plane.models.manifests import ModelManifest, StructuredRationale


@dataclass(frozen=True)
class CompletionRequest:
    context_digest: str
    context: object
    evidence_ids: list[str]
    prompt_version: str
    model_id: str | None = None
    decoding_params: dict[str, Any] | None = None
    tool_policy: str | None = None


@dataclass(frozen=True)
class CompletionResult:
    output: StructuredRationale
    manifest: ModelManifest
    request_digest: str
    response_digest: str
    token_usage: dict[str, Any] = field(default_factory=dict)


class Completer(Protocol):
    def __call__(self, request: CompletionRequest) -> CompletionResult: ...


def complete_stub(request: CompletionRequest) -> CompletionResult:
    result = stub_complete(
        request.context_digest,
        prompt_version=request.prompt_version,
        model_id=request.model_id or "curie-stub-summary",
        evidence_ids=request.evidence_ids,
    )
    return CompletionResult(
        output=result.output,
        manifest=result.manifest,
        request_digest=result.request_digest,
        response_digest=result.response_digest,
        token_usage={"prompt_tokens": 0, "completion_tokens": 0, "model": "stub"},
    )
