from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from curie_audit_plane.auth import (
    GLOBAL_ACCESS_SCOPE,
    AuthConfig,
    Principal,
    auth_from_settings,
    authorization_dependency,
    has_permission,
)
from curie_audit_plane.fhir.projection import project_audit_events, project_provenance
from curie_audit_plane.integrity.chain import per_event_hash_statuses
from curie_audit_plane.models.enums import HumanActionStatus
from curie_audit_plane.models.manifests import StructuredRationale
from curie_audit_plane.pipeline import Pipeline, TransactionResult
from curie_audit_plane.research import research_export
from curie_audit_plane.store.content import CONTENT_REF_PATTERN
from curie_audit_plane.views import sankey_view

TerminalAction = Literal["ACCEPT", "MODIFY", "REJECT"]


class RunRequest(BaseModel):
    human_action: TerminalAction | None = None
    comment: str = ""
    prompt_version: str = "clinical-summary.v1"


class ReviewRequest(BaseModel):
    action: TerminalAction
    comment: str = ""
    modified_output: StructuredRationale | None = None
    override_policy_version: str | None = None


def _serialize(result: TransactionResult) -> dict[str, object]:
    return {
        "transaction": result.transaction.__dict__,
        "overview": result.overview.model_dump(mode="json"),
        "verification": result.verification.model_dump(mode="json"),
        "output": None,
        "event_count": len(result.events),
    }


def create_app(pipeline: Pipeline, auth: AuthConfig | None = None) -> FastAPI:
    auth_config = auth if auth is not None else auth_from_settings()
    app = FastAPI(title="Curie Audit Plane", version="0.1.0")
    app.state.pipeline = pipeline
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5174",
            "http://127.0.0.1:5175",
            "http://localhost:5175",
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def _auth(permission: str):
        return authorization_dependency(auth_config, permission, pipeline)

    def _tx(transaction_id: str, principal: Principal, action: str, endpoint: str) -> TransactionResult:
        try:
            return pipeline.load_result(transaction_id)
        except KeyError as exc:
            _access(transaction_id, principal, action, endpoint, result="missing")
            raise HTTPException(status_code=404, detail="transaction not found") from exc

    def _access(
        transaction_id: str,
        principal: Principal,
        action: str,
        endpoint: str,
        *,
        result: str = "ok",
        extra: dict[str, object] | None = None,
    ) -> None:
        pipeline.record_access(
            transaction_id,
            actor=principal.actor,
            role=principal.role.value,
            action=action,
            endpoint=endpoint,
            result=result,
            extra=extra,
        )

    @app.post("/transactions/run")
    def run_transaction(
        body: RunRequest,
        principal: Principal = Depends(_auth("run")),
    ) -> dict[str, object]:
        result = pipeline.run_transaction(
            human_action=HumanActionStatus(body.human_action) if body.human_action else None,
            actor=principal.actor,
            role=principal.role.value,
            comment=body.comment,
            prompt_version=body.prompt_version,
        )
        _access(result.transaction.transaction_id, principal, "run", "POST /transactions/run")
        return _serialize(result)

    @app.get("/transactions")
    def list_transactions(principal: Principal = Depends(_auth("read"))) -> list[dict[str, object | None]]:
        _access(GLOBAL_ACCESS_SCOPE, principal, "list", "GET /transactions")
        return pipeline.services.audit.list_transactions()

    @app.get("/transactions/{transaction_id}")
    def get_transaction(
        transaction_id: str,
        principal: Principal = Depends(_auth("read")),
    ) -> dict[str, object]:
        result = _tx(transaction_id, principal, "access", f"GET /transactions/{transaction_id}")
        _access(transaction_id, principal, "access", f"GET /transactions/{transaction_id}")
        return _serialize(result)

    @app.get("/transactions/{transaction_id}/events")
    def get_events(
        transaction_id: str,
        principal: Principal = Depends(_auth("read")),
    ) -> dict[str, object]:
        result = _tx(transaction_id, principal, "access", f"GET /transactions/{transaction_id}/events")
        _access(transaction_id, principal, "access", f"GET /transactions/{transaction_id}/events")
        statuses = per_event_hash_statuses(result.events)
        return {
            "events": [
                {**event.model_dump(mode="json"), "hash_status": statuses.get(event.event_id, "NOT_RUN")}
                for event in result.events
            ],
            "hash_statuses": statuses,
        }

    @app.post("/transactions/{transaction_id}/verify")
    def verify(
        transaction_id: str,
        principal: Principal = Depends(_auth("verify")),
    ) -> dict[str, object]:
        result = _tx(transaction_id, principal, "verify", f"POST /transactions/{transaction_id}/verify")
        _access(transaction_id, principal, "verify", f"POST /transactions/{transaction_id}/verify")
        return result.verification.model_dump(mode="json")

    @app.post("/transactions/{transaction_id}/review")
    def review(
        transaction_id: str,
        body: ReviewRequest,
        principal: Principal = Depends(_auth("review")),
    ) -> dict[str, object]:
        try:
            result = pipeline.record_human_action(
                transaction_id,
                action=HumanActionStatus(body.action),
                actor=principal.actor,
                role=principal.role.value,
                comment=body.comment,
                modified_output=body.modified_output,
                override_policy_version=body.override_policy_version,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        _access(transaction_id, principal, "review", f"POST /transactions/{transaction_id}/review")
        return _serialize(result)

    @app.get("/transactions/{transaction_id}/output")
    def get_output(
        transaction_id: str,
        principal: Principal = Depends(_auth("output")),
    ) -> dict[str, object]:
        result = _tx(transaction_id, principal, "output", f"GET /transactions/{transaction_id}/output")
        if result.output is None:
            _access(transaction_id, principal, "output", f"GET /transactions/{transaction_id}/output", result="missing")
            raise HTTPException(status_code=404, detail="structured output not recorded")
        _access(transaction_id, principal, "output", f"GET /transactions/{transaction_id}/output")
        return {"output": result.output.model_dump(mode="json")}

    @app.post("/transactions/{transaction_id}/replay")
    def replay(
        transaction_id: str,
        principal: Principal = Depends(_auth("replay")),
    ) -> dict[str, object]:
        _tx(transaction_id, principal, "replay", f"POST /transactions/{transaction_id}/replay")
        result = pipeline.replay(transaction_id, actor=principal.actor, role=principal.role.value)
        return result.model_dump(mode="json")

    @app.get("/transactions/{transaction_id}/export")
    def export(
        transaction_id: str,
        principal: Principal = Depends(_auth("export")),
    ) -> dict[str, object]:
        result = _tx(transaction_id, principal, "export", f"GET /transactions/{transaction_id}/export")
        _access(transaction_id, principal, "export", f"GET /transactions/{transaction_id}/export")
        output = None
        if has_permission(principal.role, "output") and result.output is not None:
            _access(transaction_id, principal, "output", f"GET /transactions/{transaction_id}/export")
            output = result.output.model_dump(mode="json")
        return {
            "export_type": "clinical_authorized",
            "overview": result.overview.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in result.events],
            "verification": result.verification.model_dump(mode="json"),
            "output": output,
            "provenance": project_provenance(result),
            "audit_events": project_audit_events(result),
        }

    @app.get("/transactions/{transaction_id}/research-export")
    def research(
        transaction_id: str,
        principal: Principal = Depends(_auth("research_export")),
    ) -> dict[str, object]:
        result = _tx(
            transaction_id,
            principal,
            "research_export",
            f"GET /transactions/{transaction_id}/research-export",
        )
        _access(
            transaction_id,
            principal,
            "research_export",
            f"GET /transactions/{transaction_id}/research-export",
        )
        return research_export(result)

    @app.get("/transactions/{transaction_id}/sankey")
    def sankey(
        transaction_id: str,
        principal: Principal = Depends(_auth("read")),
    ) -> dict[str, object]:
        result = _tx(transaction_id, principal, "access", f"GET /transactions/{transaction_id}/sankey")
        _access(transaction_id, principal, "access", f"GET /transactions/{transaction_id}/sankey")
        return sankey_view(result.events)

    @app.get("/content/{digest}")
    def get_content(
        digest: str,
        principal: Principal = Depends(_auth("content")),
    ) -> dict[str, object]:
        ref = digest if digest.startswith("sha256:") else f"sha256:{digest}"
        extra: dict[str, object] = {"content_ref": ref}
        if not CONTENT_REF_PATTERN.fullmatch(ref):
            _access(GLOBAL_ACCESS_SCOPE, principal, "content", f"GET /content/{digest}", result="error", extra=extra)
            raise HTTPException(status_code=400, detail="malformed content reference")
        try:
            payload = pipeline.services.content.get(ref)
        except ValueError as exc:
            _access(GLOBAL_ACCESS_SCOPE, principal, "content", f"GET /content/{digest}", result="error", extra=extra)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            _access(GLOBAL_ACCESS_SCOPE, principal, "content", f"GET /content/{digest}", result="error", extra=extra)
            raise HTTPException(status_code=404, detail="content not found") from exc
        _access(GLOBAL_ACCESS_SCOPE, principal, "content", f"GET /content/{digest}", extra=extra)
        return {"ref": ref, "bytes": payload.decode("utf-8")}

    console_dist = Path(__file__).resolve().parents[3] / "console" / "dist"
    if console_dist.is_dir():
        assets = console_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(console_dist / "index.html")

    return app
