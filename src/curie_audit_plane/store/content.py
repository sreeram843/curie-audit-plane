import re
from pathlib import Path

from curie_audit_plane.integrity.hashing import sha256_hex

CONTENT_REF_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProtectedContentStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def digest_of(payload: bytes) -> str:
        return sha256_hex(payload)

    def put(self, payload: bytes, media_type: str) -> str:
        digest = self.digest_of(payload)
        (self.root / digest).write_bytes(payload)
        (self.root / f"{digest}.media_type").write_text(media_type, encoding="utf-8")
        return f"sha256:{digest}"

    def get(self, ref: str) -> bytes:
        if not CONTENT_REF_PATTERN.fullmatch(ref):
            raise ValueError("malformed content reference")
        digest = ref.removeprefix("sha256:")
        path = (self.root / digest).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("content reference escapes store root")
        if not path.is_file():
            raise FileNotFoundError(ref)
        payload = path.read_bytes()
        if self.digest_of(payload) != digest:
            raise ValueError("retrieved content digest mismatch")
        return payload
