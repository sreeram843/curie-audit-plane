from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from fastapi import Header, HTTPException, Request

from curie_audit_plane.config import Settings, settings


class Role(StrEnum):
    REVIEWER = "reviewer"
    INVESTIGATOR = "investigator"
    ADMIN = "admin"


GLOBAL_ACCESS_SCOPE = "access-scope:global"


PERMISSIONS: dict[str, frozenset[Role]] = {
    "run": frozenset({Role.REVIEWER, Role.INVESTIGATOR, Role.ADMIN}),
    "read": frozenset({Role.REVIEWER, Role.INVESTIGATOR, Role.ADMIN}),
    "review": frozenset({Role.REVIEWER, Role.ADMIN}),
    "verify": frozenset({Role.INVESTIGATOR, Role.ADMIN}),
    "replay": frozenset({Role.INVESTIGATOR, Role.ADMIN}),
    "export": frozenset({Role.INVESTIGATOR, Role.ADMIN}),
    "research_export": frozenset({Role.INVESTIGATOR, Role.ADMIN}),
    "content": frozenset({Role.ADMIN}),
    "output": frozenset({Role.REVIEWER, Role.ADMIN}),
}


def _digest(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def tokens_match(stored: str, provided: str) -> bool:
    return hmac.compare_digest(_digest(stored), _digest(provided))


@dataclass(frozen=True)
class Principal:
    role: Role
    actor: str


@dataclass
class AuthConfig:
    accounts: dict[str, Role]

    def resolve(self, token: str) -> Role | None:
        for stored, role in self.accounts.items():
            if tokens_match(stored, token):
                return role
        return None

    @property
    def configured(self) -> bool:
        return bool(self.accounts)


def has_permission(role: Role, permission: str) -> bool:
    return role in PERMISSIONS[permission]


def write_generated_local_tokens(env_path: Path) -> dict[str, str]:
    token = secrets.token_hex(32)
    assigned = {"CAP_ADMIN_TOKEN": token, "VITE_CAP_AUTH_TOKEN": token}
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in assigned:
                output.append(f"{key}={assigned[key]}")
                seen.add(key)
                continue
        output.append(line)
    for key, value in assigned.items():
        if key not in seen:
            output.append(f"{key}={value}")
    env_path.write_text("\n".join(output) + "\n")
    return assigned


def auth_from_settings(cfg: Settings | None = None) -> AuthConfig:
    cfg = cfg or settings
    accounts: dict[str, Role] = {}
    if cfg.reviewer_token:
        accounts[cfg.reviewer_token] = Role.REVIEWER
    if cfg.investigator_token:
        accounts[cfg.investigator_token] = Role.INVESTIGATOR
    if cfg.admin_token:
        accounts[cfg.admin_token] = Role.ADMIN
    return AuthConfig(accounts=accounts)


def require_principal(auth: AuthConfig, authorization: str | None, permission: str) -> Principal:
    if not auth.configured:
        raise HTTPException(status_code=503, detail="protected-content token is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    role = auth.resolve(token)
    if role is None:
        raise HTTPException(status_code=401, detail="invalid token")
    allowed = PERMISSIONS[permission]
    if role not in allowed:
        raise HTTPException(status_code=403, detail="insufficient role")
    return Principal(role=role, actor=f"{role.value}@curie.local")


def authorization_dependency(auth: AuthConfig, permission: str, pipeline: object | None = None):
    def _inner(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> Principal:
        try:
            return require_principal(auth, authorization, permission)
        except HTTPException as exc:
            if pipeline is not None and exc.status_code in {401, 403}:
                transaction_id = request.path_params.get("transaction_id") or GLOBAL_ACCESS_SCOPE
                actor = "anonymous"
                role = "unauthenticated"
                if authorization and authorization.lower().startswith("bearer "):
                    token = authorization.split(" ", 1)[1].strip()
                    resolved = auth.resolve(token) if token else None
                    if resolved is not None:
                        actor = f"{resolved.value}@curie.local"
                        role = resolved.value
                recorder = getattr(pipeline, "record_access", None)
                if callable(recorder):
                    recorder(
                        transaction_id,
                        actor=actor,
                        role=role,
                        action=permission,
                        endpoint=f"{request.method} {request.url.path}",
                        result="denied",
                    )
            raise

    return _inner
