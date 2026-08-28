import re

from curie_audit_plane.integrity.hashing import sha256_hex

COMMENT_MAX_LENGTH = 500
_MRN_RE = re.compile(r"TEST-\d{5}")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def sanitize_comment(comment: str) -> dict[str, object]:
    raw = comment or ""
    digest = sha256_hex(raw.encode("utf-8")) if raw else ""
    if not raw:
        return {
            "comment": "",
            "comment_present": False,
            "comment_redacted": False,
            "comment_digest": "",
        }
    if _MRN_RE.search(raw) or _SSN_RE.search(raw):
        return {
            "comment": "",
            "comment_present": True,
            "comment_redacted": True,
            "comment_digest": digest,
        }
    truncated = raw[:COMMENT_MAX_LENGTH]
    return {
        "comment": truncated,
        "comment_present": True,
        "comment_redacted": len(raw) > COMMENT_MAX_LENGTH,
        "comment_digest": digest,
    }
