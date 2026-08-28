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
_OPAQUE_SALT = b"curie-audit-plane-opaque-v1"


def opaque_identifier(value: str) -> str:
    digest = hashlib.sha256(_OPAQUE_SALT + value.encode("utf-8")).hexdigest()[:20]
    return f"tok_{digest}"


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
