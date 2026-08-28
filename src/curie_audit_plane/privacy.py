from __future__ import annotations

import hashlib

COMMENT_CATEGORIES = frozenset(
    {
        "unspecified",
        "accept_as_recorded",
        "modify_for_accuracy",
        "reject_insufficient_evidence",
        "policy_override",
    }
)
ALLOWED_PURPOSES = frozenset({"synthetic-encounter-summary"})
ALLOWED_PROMPT_VERSIONS = frozenset({"clinical-summary.v1", "clinical-summary.v2"})
ALLOWED_OVERRIDE_POLICIES = frozenset({"override.v1"})
MAX_VERSION_LEN = 64
_OPAQUE_SALT = b"curie-audit-plane-opaque-v1"


def opaque_identifier(value: str) -> str:
    digest = hashlib.sha256(_OPAQUE_SALT + value.encode("utf-8")).hexdigest()[:20]
    return f"tok_{digest}"


def sanitize_purpose(purpose: str) -> str:
    """Keep only an allowlisted purpose or an opaque token on the audit chain."""
    value = (purpose or "").strip()
    if value in ALLOWED_PURPOSES:
        return value
    if value.startswith("tok_") and len(value) > 4 and value[4:].isalnum():
        return value
    return opaque_identifier(value or "unspecified")


def sanitize_prompt_version(prompt_version: str) -> str:
    value = (prompt_version or "").strip()
    if len(value) > MAX_VERSION_LEN or value not in ALLOWED_PROMPT_VERSIONS:
        raise ValueError("prompt_version is not allowlisted")
    return value


def sanitize_override_policy_version(override_policy_version: str | None) -> str | None:
    if override_policy_version is None:
        return None
    value = override_policy_version.strip()
    if not value:
        return None
    if len(value) > MAX_VERSION_LEN or value not in ALLOWED_OVERRIDE_POLICIES:
        raise ValueError("override_policy_version is not allowlisted")
    return value


def sanitize_comment(comment: str, category: str = "unspecified") -> dict[str, object]:
    """Keep only a controlled category in immutable metadata.

    Detailed reviewer text must be stored in the protected-content store, not
    on the audit chain. No digest of the free-text comment is recorded in
    metadata because a digest can leak low-entropy PHI.
    """
    raw = comment or ""
    selected = category if category in COMMENT_CATEGORIES else "unspecified"
    return {
        "comment": "",
        "comment_category": selected,
        "comment_present": bool(raw.strip()),
        "comment_redacted": True,
    }
