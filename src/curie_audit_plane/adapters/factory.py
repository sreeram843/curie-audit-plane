import httpx

from curie_audit_plane.adapters.completion import Completer, CompletionRequest, complete_stub
from curie_audit_plane.adapters.openai_compatible import (
    complete_openai_compatible,
    normalize_base_url,
    resolve_chat_model,
)
from curie_audit_plane.config import Settings, settings


def completer_from_settings(cfg: Settings | None = None) -> Completer:
    cfg = cfg or settings
    if cfg.llm_provider != "openai_compatible":
        return complete_stub

    def _complete(request: CompletionRequest):
        model = cfg.llm_model
        if not model or model == "curie-stub-summary":
            endpoint = normalize_base_url(cfg.llm_base_url)
            with httpx.Client(timeout=cfg.llm_timeout_seconds) as client:
                listing = client.get(f"{endpoint}/models")
                listing.raise_for_status()
                model = resolve_chat_model(listing.json(), preferred=cfg.llm_model)
        return complete_openai_compatible(
            request,
            base_url=cfg.llm_base_url,
            model=model,
            api_key=cfg.llm_api_key,
            timeout_seconds=cfg.llm_timeout_seconds,
        )

    return _complete
