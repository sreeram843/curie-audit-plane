import json

import httpx
import pytest

from curie_audit_plane.adapters.openai_compatible import (
    CompletionRequest,
    complete_openai_compatible,
    parse_rationale_content,
    resolve_chat_model,
    sanitize_llm_endpoint,
    validate_llm_endpoint,
)
from curie_audit_plane.models.manifests import StructuredRationale

VALID_RATIONALE = {
    "summary": "Office visit with elevated blood pressure on lisinopril.",
    "findings": [
        {
            "text": "Office blood pressure 148/92 mmHg",
            "evidence_refs": ["obs-bp-TEST-00001"],
        }
    ],
    "evidence_references": ["obs-bp-TEST-00001", "htn-bp-target.v1"],
    "uncertainty": "Home readings unavailable.",
    "assumptions": ["The bounded context is complete."],
    "missing_data": ["Home blood pressure series"],
    "follow_up_questions": ["Has the patient taken lisinopril this morning?"],
}


def test_resolve_chat_model_skips_embedding_models():
    models = {
        "data": [
            {"id": "text-embedding-nomic-embed-text-v1.5"},
            {"id": "medgemma-4b-it-mlx"},
        ]
    }
    assert resolve_chat_model(models, preferred="") == "medgemma-4b-it-mlx"
    assert resolve_chat_model(models, preferred="medgemma-4b-it-mlx") == "medgemma-4b-it-mlx"


def test_parse_rationale_accepts_fenced_json_and_rejects_hidden_reasoning():
    fenced = "```json\n" + json.dumps(VALID_RATIONALE) + "\n```"
    parsed = parse_rationale_content(fenced)
    assert parsed.summary.startswith("Office visit")
    with pytest.raises(ValueError, match="structured rationale schema"):
        parse_rationale_content(json.dumps({**VALID_RATIONALE, "chain_of_thought": "hidden"}))


def test_complete_records_lm_studio_manifest_and_token_usage():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "model": "medgemma-4b-it-mlx",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(VALID_RATIONALE),
                            "reasoning_content": "do-not-persist",
                        }
                    }
                ],
                "usage": {"prompt_tokens": 128, "completion_tokens": 64, "total_tokens": 192},
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://127.0.0.1:1234/v1",
    )
    result = complete_openai_compatible(
        CompletionRequest(
            context_digest="abc123",
            context=[{"resourceType": "Observation", "id": "obs-bp-TEST-00001"}],
            evidence_ids=["obs-bp-TEST-00001", "htn-bp-target.v1"],
            prompt_version="clinical-summary.v1",
            model_id="medgemma-4b-it-mlx",
        ),
        base_url="http://127.0.0.1:1234/v1",
        model="medgemma-4b-it-mlx",
        client=client,
    )
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "medgemma-4b-it-mlx"
    assert body["temperature"] == 0
    assert body["response_format"]["type"] == "json_schema"
    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert result.manifest.provider_id == "lmstudio"
    assert result.manifest.endpoint == "http://127.0.0.1:1234/v1"
    assert result.manifest.model_id == "medgemma-4b-it-mlx"
    assert result.manifest.runtime == "openai-compatible"
    assert result.token_usage["prompt_tokens"] == 128
    assert result.token_usage["completion_tokens"] == 64
    StructuredRationale.model_validate(result.output.model_dump())
    assert "chain_of_thought" not in result.output.model_dump()


def test_complete_reuses_recorded_decoding_params():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "medgemma-4b-it-mlx",
                "choices": [{"message": {"content": json.dumps(VALID_RATIONALE)}}],
                "usage": {},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://127.0.0.1:1234/v1")
    complete_openai_compatible(
        CompletionRequest(
            context_digest="abc123",
            context=[],
            evidence_ids=["obs-bp-TEST-00001"],
            prompt_version="clinical-summary.v1",
            decoding_params={
                "temperature": 0.2,
                "seed": 7,
                "top_p": 0.9,
                "response_format": {"type": "json_object"},
                "presence_penalty": 0.1,
            },
            tool_policy="knowledge.lookup",
        ),
        base_url="http://127.0.0.1:1234/v1",
        model="medgemma-4b-it-mlx",
        client=client,
    )
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["temperature"] == 0.2
    assert body["seed"] == 7
    assert body["top_p"] == 0.9
    assert body["response_format"] == {"type": "json_object"}
    assert body["presence_penalty"] == 0.1


def test_validate_llm_endpoint_rejects_credentials_and_unapproved_hosts():
    with pytest.raises(ValueError, match="userinfo"):
        validate_llm_endpoint("http://user:secret@127.0.0.1:1234/v1")
    with pytest.raises(ValueError, match="query"):
        validate_llm_endpoint("http://127.0.0.1:1234/v1?api_key=secret")
    with pytest.raises(ValueError, match="approved"):
        validate_llm_endpoint("https://api.openai.com/v1")
    assert validate_llm_endpoint("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1"
    assert sanitize_llm_endpoint("http://127.0.0.1:1234/v1") == "http://127.0.0.1:1234/v1"
