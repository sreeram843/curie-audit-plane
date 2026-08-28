from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from curie_audit_plane.adapters.completion import CompletionRequest, CompletionResult
from curie_audit_plane.integrity.canonical import canonicalize
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.models.manifests import ModelManifest, StructuredRationale

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def normalize_base_url(url: str) -> str:
    trimmed = url.rstrip("/")
    if trimmed.endswith("/v1"):
        return trimmed
    return f"{trimmed}/v1"


def resolve_chat_model(payload: Mapping[str, Any], preferred: str = "") -> str:
    ids = [
        str(item["id"])
        for item in payload.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    if preferred and preferred in ids:
        return preferred
    for model_id in ids:
        if "embed" in model_id.lower():
            continue
        return model_id
    if preferred:
        return preferred
    raise ValueError("no chat model available from OpenAI-compatible endpoint")


def parse_rationale_content(content: str) -> StructuredRationale:
    text = _FENCE_RE.sub("", content.strip()).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("model response was not valid JSON") from exc
    try:
        return StructuredRationale.model_validate(data)
    except ValidationError as exc:
        raise ValueError("model response did not match structured rationale schema") from exc


def _system_prompt(evidence_ids: list[str], prompt_version: str) -> str:
    allowed = ", ".join(evidence_ids) if evidence_ids else "(none provided)"
    return (
        f"You are a clinical documentation assistant for prompt {prompt_version}. "
        "Summarize the bounded synthetic FHIR context for a human clinician reviewer. "
        "Return ONLY a JSON object with keys: summary, findings, evidence_references, "
        "uncertainty, assumptions, missing_data, follow_up_questions. "
        "findings is an array of objects with keys text and evidence_refs. "
        "Do not include chain_of_thought, hidden reasoning, or any other keys. "
        "Cite only these evidence IDs: "
        f"{allowed}. Do not invent identifiers. This is synthetic data, not a diagnosis."
    )


def complete_openai_compatible(
    request: CompletionRequest,
    *,
    base_url: str,
    model: str,
    api_key: str = "",
    timeout_seconds: float = 120,
    client: httpx.Client | None = None,
) -> CompletionResult:
    endpoint = normalize_base_url(base_url)
    messages = [
        {"role": "system", "content": _system_prompt(request.evidence_ids, request.prompt_version)},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "context_digest": request.context_digest,
                    "allowed_evidence_ids": request.evidence_ids,
                    "bounded_context": request.context,
                },
                default=str,
            ),
        },
    ]
    params = request.decoding_params or {}
    temperature = params.get("temperature", 0)
    recorded_format = params.get("response_format")
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": recorded_format
        if isinstance(recorded_format, dict)
        else {
            "type": "json_schema",
            "json_schema": {
                "name": "structured_rationale",
                "strict": True,
                "schema": StructuredRationale.model_json_schema(),
            },
        },
    }
    for key in ("seed", "top_p", "max_tokens", "top_k", "presence_penalty", "frequency_penalty", "stop"):
        if key in params and params[key] is not None:
            body[key] = params[key]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    requested_at = datetime.now(UTC)
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout_seconds)
    try:
        response = http.post(f"{endpoint}/chat/completions", json=body, headers=headers)
        response.raise_for_status()
        payload = response.json()
    finally:
        if owns_client:
            http.close()
    responded_at = datetime.now(UTC)
    choices = payload.get("choices") or []
    if not choices:
        raise ValueError("OpenAI-compatible endpoint returned no choices")
    content = str(choices[0].get("message", {}).get("content") or "")
    # Ignore provider reasoning_content; it is not part of the audit contract.
    output = parse_rationale_content(content)
    usage = payload.get("usage") or {}
    token_usage = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "model": payload.get("model") or model,
    }
    returned_model = str(payload.get("model") or model)
    manifest = ModelManifest(
        model_id=returned_model,
        provider_id="lmstudio",
        endpoint=endpoint,
        model_version=returned_model,
        prompt_version=request.prompt_version,
        decoding_params={
            "temperature": temperature,
            "response_format": params.get("response_format", "json_schema"),
            **{key: value for key, value in params.items() if key not in {"temperature", "response_format"}},
        },
        tool_policy=request.tool_policy or "knowledge.lookup",
        runtime="openai-compatible",
        seed=0,
        requested_at=requested_at,
        responded_at=responded_at,
    )
    return CompletionResult(
        output=output,
        manifest=manifest,
        request_digest=sha256_hex(canonicalize(body)),
        response_digest=sha256_hex(canonicalize(output.model_dump(mode="json"))),
        token_usage=token_usage,
    )
