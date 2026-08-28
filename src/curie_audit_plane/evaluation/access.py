from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from curie_audit_plane.api.app import create_app
from curie_audit_plane.auth import AuthConfig, Role
from curie_audit_plane.evaluation.harness import _isolated_pipeline
from curie_audit_plane.evaluation.stats import rate_summary
from curie_audit_plane.pipeline import Pipeline

ADMIN = "eval-admin-token"
REVIEWER = "eval-reviewer-token"
INVESTIGATOR = "eval-investigator-token"


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def run_access_control_evaluation(pipeline: Pipeline) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="curie-access-") as temp:
        isolated = _isolated_pipeline(pipeline, Path(temp))
        client = TestClient(
            create_app(
                isolated,
                auth=AuthConfig(
                    accounts={
                        ADMIN: Role.ADMIN,
                        REVIEWER: Role.REVIEWER,
                        INVESTIGATOR: Role.INVESTIGATOR,
                    }
                ),
            )
        )
        created = client.post(
            "/transactions/run",
            json={"human_action": "ACCEPT", "actor": "reviewer@curie.local"},
            headers=_headers(ADMIN),
        )
        tx_id = created.json()["transaction"]["transaction_id"]
        events = client.get(f"/transactions/{tx_id}/events", headers=_headers(ADMIN)).json()["events"]
        context = next(event for event in events if event["event_type"] == "context.manifest.created")
        digest = str(context["payload_ref"]).removeprefix("sha256:")
        probes = [
            ("reviewer_read", REVIEWER, f"/transactions/{tx_id}", "GET", 200),
            ("investigator_verify", INVESTIGATOR, f"/transactions/{tx_id}/verify", "POST", 200),
            ("admin_content", ADMIN, f"/content/{digest}", "GET", 200),
            ("denied_unauthenticated", "", "/transactions", "GET", 401),
            ("reviewer_denied_export", REVIEWER, f"/transactions/{tx_id}/export", "GET", 403),
            ("investigator_denied_output", INVESTIGATOR, f"/transactions/{tx_id}/output", "GET", 403),
            ("investigator_denied_content", INVESTIGATOR, f"/content/{digest}", "GET", 403),
            ("reviewer_output", REVIEWER, f"/transactions/{tx_id}/output", "GET", 200),
            ("investigator_export", INVESTIGATOR, f"/transactions/{tx_id}/export", "GET", 200),
            ("missing_transaction", ADMIN, "/transactions/missing-transaction-id", "GET", 404),
            ("global_scope_list", ADMIN, "/transactions", "GET", 200),
        ]
        cases: list[dict[str, object]] = []
        passed = 0
        for name, token, path, method, expected in probes:
            headers = _headers(token) if token else {}
            if method == "POST":
                response = client.post(path, headers=headers)
            else:
                response = client.get(path, headers=headers)
            ok = response.status_code == expected
            passed += int(ok)
            cases.append(
                {
                    "name": name,
                    "role": token or "unauthenticated",
                    "method": method,
                    "path": path.replace(tx_id, "{transaction_id}").replace(digest, "{digest}"),
                    "expected_status": expected,
                    "observed_status": response.status_code,
                    "passed": ok,
                }
            )
        isolated.close()
    return {
        "cases": cases,
        "pass_rate": rate_summary(passed, len(cases)),
    }
