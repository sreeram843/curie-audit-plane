from __future__ import annotations

from typing import Any

from curie_audit_plane.models.manifests import StructuredRationale


def _normalize(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "summary": " ".join(str(payload.get("summary", "")).split()),
        "findings": payload.get("findings") or [],
        "evidence_references": sorted(payload.get("evidence_references") or []),
        "uncertainty": " ".join(str(payload.get("uncertainty", "")).split()),
        "assumptions": sorted(payload.get("assumptions") or []),
        "missing_data": sorted(payload.get("missing_data") or []),
        "follow_up_questions": sorted(payload.get("follow_up_questions") or []),
    }


def classify_replay_outputs(
    original: StructuredRationale,
    replayed: StructuredRationale,
) -> tuple[str, list[str]]:
    orig = original.model_dump(mode="json")
    new = replayed.model_dump(mode="json")
    if orig == new:
        return "EXACT_MATCH", []
    if _normalize(orig) == _normalize(new):
        return "EQUIVALENT", ["non-semantic fields differ"]
    reasons: list[str] = []
    if _normalize(orig)["summary"] != _normalize(new)["summary"]:
        reasons.append("summary differs")
    if orig.get("findings") != new.get("findings"):
        reasons.append("findings differ")
    if orig.get("evidence_references") != new.get("evidence_references"):
        reasons.append("evidence references differ")
    if orig.get("uncertainty") != new.get("uncertainty"):
        reasons.append("uncertainty differs")
    return "DIVERGENT", reasons or ["structured output digest differs"]


def finalize_replay_result(
    *,
    runtime: str,
    endpoint: str,
    classification: str,
    reasons: list[str] | None = None,
) -> tuple[str, list[str]]:
    notes = list(reasons or [])
    runtime = runtime or ""
    endpoint = (endpoint or "").strip()
    if runtime == "openai-compatible":
        if not endpoint:
            return "NOT_REPLAYABLE", notes + ["hosted model endpoint is missing"]
        if classification == "EXACT_MATCH":
            return "EQUIVALENT", notes + ["hosted model replay is not bit-exact"]
        return classification, notes
    if runtime == "deterministic-stub":
        return classification, notes
    if not runtime or not endpoint:
        return "NOT_REPLAYABLE", notes + ["recorded execution configuration is incomplete"]
    if classification == "EXACT_MATCH":
        return "EQUIVALENT", notes + ["uncontrolled runtime replay is not bit-exact"]
    return classification, notes
