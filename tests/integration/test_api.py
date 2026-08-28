from fastapi.testclient import TestClient

from curie_audit_plane.api.app import create_app
from curie_audit_plane.auth import AuthConfig, Role
from curie_audit_plane.integrity.signing import generate_keypair
from curie_audit_plane.pipeline import Pipeline, PipelineServices
from curie_audit_plane.store.audit import AuditStore
from curie_audit_plane.store.content import ProtectedContentStore

ADMIN = "test-admin-token"
REVIEWER = "test-reviewer-token"
INVESTIGATOR = "test-investigator-token"


def _headers(token: str = ADMIN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _client(tmp_path, auth: AuthConfig | None = None) -> TestClient:
    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        )
    )
    config = auth or AuthConfig(
        accounts={
            ADMIN: Role.ADMIN,
            REVIEWER: Role.REVIEWER,
            INVESTIGATOR: Role.INVESTIGATOR,
        }
    )
    return TestClient(create_app(pipeline, auth=config))


def test_run_verify_review_export_and_sankey(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/transactions/run",
        json={"human_action": "ACCEPT", "actor": "reviewer@curie.local"},
        headers=_headers(),
    )
    assert created.status_code == 200
    body = created.json()
    tx_id = body["transaction"]["transaction_id"]
    assert body["transaction"]["status"] == "COMPLETED"
    listed = client.get("/transactions", headers=_headers())
    assert any(item["transaction_id"] == tx_id for item in listed.json())
    detail = client.get(f"/transactions/{tx_id}", headers=_headers())
    assert detail.status_code == 200
    events = client.get(f"/transactions/{tx_id}/events", headers=_headers())
    assert events.status_code == 200
    assert events.json()["events"]
    verified = client.post(f"/transactions/{tx_id}/verify", headers=_headers())
    assert verified.json()["status"] == "VERIFIED"
    sankey = client.get(f"/transactions/{tx_id}/sankey", headers=_headers())
    payload = sankey.json()
    assert payload["metric"] == "artifact_count"
    assert "causal" not in payload["caption"].lower() or "not imply causal" in payload["caption"].lower()
    export = client.get(f"/transactions/{tx_id}/export", headers=_headers())
    assert export.status_code == 200
    assert export.json()["provenance"]["resourceType"] == "Provenance"
    assert export.json()["export_type"] == "clinical_authorized"
    replay = client.post(f"/transactions/{tx_id}/replay", headers=_headers())
    assert replay.json()["result"] == "EXACT_MATCH"
    assert replay.json()["original_output"]["summary"]
    assert replay.json()["replay_output"]["summary"]
    assert "modified_output" in replay.json()
    research = client.get(f"/transactions/{tx_id}/research-export", headers=_headers())
    assert research.status_code == 200
    assert research.json()["export_type"] == "research"
    assert "TEST-00001" not in research.text


def test_review_modify_via_api(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    reviewed = client.post(
        f"/transactions/{tx_id}/review",
        json={
            "action": "MODIFY",
            "actor": "reviewer@curie.local",
            "role": "clinical-reviewer",
            "comment": "adjusted",
            "modified_output": {
                "summary": "Clinician-adjusted summary.",
                "findings": [{"text": "BP remains high", "evidence_refs": ["obs-bp-TEST-00001"]}],
                "evidence_references": ["obs-bp-TEST-00001"],
                "uncertainty": "Home readings still missing.",
                "assumptions": [],
                "missing_data": ["Home BP"],
                "follow_up_questions": [],
            },
        },
        headers=_headers(),
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["transaction"]["human_action"] == "MODIFY"


def test_api_rejects_pending_as_human_disposition(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers())
    assert created.status_code == 200
    assert created.json()["transaction"]["status"] == "WAITING_FOR_REVIEW"
    assert created.json()["transaction"]["human_action"] == "PENDING"
    tx_id = created.json()["transaction"]["transaction_id"]
    run_pending = client.post(
        "/transactions/run",
        json={"human_action": "PENDING", "actor": "reviewer@curie.local"},
        headers=_headers(),
    )
    assert run_pending.status_code in {400, 422}
    reviewed = client.post(
        f"/transactions/{tx_id}/review",
        json={"action": "PENDING", "actor": "reviewer@curie.local"},
        headers=_headers(),
    )
    assert reviewed.status_code in {400, 422}


def test_missing_token_is_unauthorized(tmp_path):
    client = _client(tmp_path)
    response = client.get("/transactions")
    assert response.status_code == 401


def test_wrong_token_is_unauthorized(tmp_path):
    client = _client(tmp_path)
    response = client.get("/transactions", headers=_headers("nope"))
    assert response.status_code == 401


def test_unconfigured_token_fails_closed(tmp_path):
    client = _client(tmp_path, auth=AuthConfig(accounts={}))
    response = client.get("/transactions", headers=_headers())
    assert response.status_code == 503


def test_reviewer_cannot_access_protected_content_or_export(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT", "actor": "r"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    events = client.get(f"/transactions/{tx_id}/events", headers=_headers(REVIEWER))
    assert events.status_code == 200
    export = client.get(f"/transactions/{tx_id}/export", headers=_headers(REVIEWER))
    assert export.status_code == 403
    verify = client.post(f"/transactions/{tx_id}/verify", headers=_headers(REVIEWER))
    assert verify.status_code == 403
    digest = "0" * 64
    content = client.get(f"/content/{digest}", headers=_headers(REVIEWER))
    assert content.status_code == 403


def test_investigator_can_verify_but_not_read_content(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT", "actor": "r"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    verify = client.post(f"/transactions/{tx_id}/verify", headers=_headers(INVESTIGATOR))
    assert verify.status_code == 200
    review = client.post(
        f"/transactions/{tx_id}/review",
        json={"action": "ACCEPT", "actor": "r"},
        headers=_headers(INVESTIGATOR),
    )
    assert review.status_code == 403
    content = client.get(f"/content/{'0' * 64}", headers=_headers(INVESTIGATOR))
    assert content.status_code == 403


def test_malformed_content_reference_is_bad_request(tmp_path):
    client = _client(tmp_path)
    response = client.get("/content/not-a-digest", headers=_headers())
    assert response.status_code == 400


def test_admin_can_read_authorized_content(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT", "actor": "r"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    events = client.get(f"/transactions/{tx_id}/events", headers=_headers()).json()["events"]
    context = next(event for event in events if event["event_type"] == "context.manifest.created")
    ref = context["payload_ref"]
    digest = ref.removeprefix("sha256:")
    response = client.get(f"/content/{digest}", headers=_headers())
    assert response.status_code == 200
    assert response.json()["ref"] == ref


def test_review_and_run_bind_actor_to_authenticated_principal(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers(REVIEWER))
    tx_id = created.json()["transaction"]["transaction_id"]
    reviewed = client.post(
        f"/transactions/{tx_id}/review",
        json={"action": "ACCEPT", "actor": "attacker@example.com", "role": "admin"},
        headers=_headers(REVIEWER),
    )
    assert reviewed.status_code == 200
    events = client.get(f"/transactions/{tx_id}/events", headers=_headers(REVIEWER)).json()["events"]
    human = next(event for event in events if event["event_type"] == "human.action_recorded")
    assert human["payload_metadata"]["actor"] == "reviewer@curie.local"
    assert human["payload_metadata"]["role"] == "reviewer"


def test_ordinary_read_omits_protected_output(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    detail = client.get(f"/transactions/{tx_id}", headers=_headers(INVESTIGATOR))
    assert detail.status_code == 200
    assert detail.json().get("output") is None
    denied = client.get(f"/transactions/{tx_id}/output", headers=_headers(INVESTIGATOR))
    assert denied.status_code == 403
    allowed = client.get(f"/transactions/{tx_id}/output", headers=_headers(REVIEWER))
    assert allowed.status_code == 200
    assert allowed.json()["output"]["summary"]


def test_visualization_run_and_review_are_access_audited(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    client.get(f"/transactions/{tx_id}/sankey", headers=_headers())
    client.post(
        f"/transactions/{tx_id}/review",
        json={"action": "ACCEPT", "comment": "ok"},
        headers=_headers(),
    )
    access = client.app.state.pipeline.services.audit.list_access_events(tx_id)
    actions = {event.payload_metadata["action"] for event in access}
    endpoints = {event.payload_metadata["endpoint"] for event in access}
    assert "run" in actions
    assert "review" in actions
    assert any("sankey" in str(endpoint) for endpoint in endpoints)


def test_run_and_review_omit_structured_output(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers(REVIEWER))
    assert created.status_code == 200
    assert created.json().get("output") is None
    tx_id = created.json()["transaction"]["transaction_id"]
    listed = client.get("/transactions", headers=_headers(REVIEWER))
    assert listed.status_code == 200
    assert all("output" not in item or item.get("output") is None for item in listed.json())
    reviewed = client.post(
        f"/transactions/{tx_id}/review",
        json={"action": "ACCEPT", "comment": "ok"},
        headers=_headers(REVIEWER),
    )
    assert reviewed.status_code == 200
    assert reviewed.json().get("output") is None
    output = client.get(f"/transactions/{tx_id}/output", headers=_headers(REVIEWER))
    assert output.status_code == 200
    assert output.json()["output"]["summary"]
    admin_output = client.get(f"/transactions/{tx_id}/output", headers=_headers())
    assert admin_output.status_code == 200


def test_role_boundaries_for_output_verify_and_content(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    assert client.get(f"/transactions/{tx_id}/output", headers=_headers(INVESTIGATOR)).status_code == 403
    assert client.get(f"/transactions/{tx_id}/output", headers=_headers(REVIEWER)).status_code == 200
    assert client.post(f"/transactions/{tx_id}/verify", headers=_headers(REVIEWER)).status_code == 403
    assert client.post(f"/transactions/{tx_id}/verify", headers=_headers(INVESTIGATOR)).status_code == 200
    assert client.get(f"/content/{'0' * 64}", headers=_headers(REVIEWER)).status_code == 403
    assert client.get(f"/content/{'0' * 64}", headers=_headers(INVESTIGATOR)).status_code == 403


def test_list_and_content_reads_are_access_audited(tmp_path):
    from curie_audit_plane.auth import GLOBAL_ACCESS_SCOPE

    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    assert client.get("/transactions", headers=_headers()).status_code == 200
    events = client.get(f"/transactions/{tx_id}/events", headers=_headers()).json()["events"]
    context = next(event for event in events if event["event_type"] == "context.manifest.created")
    digest = context["payload_ref"].removeprefix("sha256:")
    assert client.get(f"/content/{digest}", headers=_headers()).status_code == 200
    denied = client.get(f"/content/{digest}", headers=_headers(REVIEWER))
    assert denied.status_code == 403
    pipeline = client.app.state.pipeline
    global_access = pipeline.services.audit.list_access_events(GLOBAL_ACCESS_SCOPE)
    actions = {(event.payload_metadata["action"], event.payload_metadata["result"]) for event in global_access}
    assert ("list", "ok") in actions
    assert ("content", "ok") in actions
    assert ("content", "denied") in actions
    content_ok = next(
        event
        for event in global_access
        if event.payload_metadata["action"] == "content" and event.payload_metadata["result"] == "ok"
    )
    assert content_ok.payload_metadata["content_ref"].endswith(digest)
    assert content_ok.payload_metadata["actor"] == "admin@curie.local"
    denied_event = next(
        event
        for event in global_access
        if event.payload_metadata["action"] == "content" and event.payload_metadata["result"] == "denied"
    )
    assert denied_event.payload_metadata["actor"] == "reviewer@curie.local"


def test_denied_transaction_output_is_access_audited(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    denied = client.get(f"/transactions/{tx_id}/output", headers=_headers(INVESTIGATOR))
    assert denied.status_code == 403
    allowed = client.get(f"/transactions/{tx_id}/output", headers=_headers(REVIEWER))
    assert allowed.status_code == 200
    access = client.app.state.pipeline.services.audit.list_access_events(tx_id)
    output_events = [event for event in access if event.payload_metadata["action"] == "output"]
    results = {event.payload_metadata["result"] for event in output_events}
    assert "denied" in results
    assert "ok" in results


def test_events_report_tampered_hash_when_payload_changes(tmp_path):
    import json

    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    pipeline = client.app.state.pipeline
    stored = pipeline.services.audit.list_events(tx_id)
    target = next(event for event in stored if event.event_type.value == "model.requested")
    neighbors = [event for event in stored if event.sequence_number in {target.sequence_number - 1, target.sequence_number + 1}]
    tampered = target.model_copy(
        update={"payload_metadata": {**target.payload_metadata, "purpose": "altered-without-rehash"}}
    )
    assert tampered.event_hash == target.event_hash
    pipeline.services.audit._conn.execute(
        "UPDATE events SET event_json = ? WHERE event_id = ?",
        (json.dumps(tampered.model_dump(mode="json")), target.event_id),
    )
    pipeline.services.audit._conn.commit()
    payload = client.get(f"/transactions/{tx_id}/events", headers=_headers()).json()
    by_id = {event["event_id"]: event for event in payload["events"]}
    assert by_id[target.event_id]["hash_status"] == "TAMPERED"
    for neighbor in neighbors:
        assert by_id[neighbor.event_id]["hash_status"] == "VERIFIED"
    assert payload["hash_statuses"][target.event_id] == "TAMPERED"


def test_access_events_do_not_break_integrity_verification(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT", "actor": "r"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    client.get(f"/transactions/{tx_id}", headers=_headers())
    client.get(f"/transactions/{tx_id}/export", headers=_headers())
    verified = client.post(f"/transactions/{tx_id}/verify", headers=_headers())
    assert verified.json()["status"] == "VERIFIED"
    clinical = client.get(f"/transactions/{tx_id}/events", headers=_headers()).json()["events"]
    assert not any(event["event_type"] == "ui.access_recorded" for event in clinical)


def test_clinical_export_includes_output_only_with_output_permission(tmp_path):
    client = _client(tmp_path)
    created = client.post("/transactions/run", json={"human_action": "ACCEPT"}, headers=_headers())
    tx_id = created.json()["transaction"]["transaction_id"]
    investigator = client.get(f"/transactions/{tx_id}/export", headers=_headers(INVESTIGATOR))
    assert investigator.status_code == 200
    assert investigator.json().get("output") is None
    admin = client.get(f"/transactions/{tx_id}/export", headers=_headers())
    assert admin.status_code == 200
    assert admin.json()["output"]["summary"]
    access = client.app.state.pipeline.services.audit.list_access_events(tx_id)
    output_from_export = [
        event
        for event in access
        if event.payload_metadata["action"] == "output" and "export" in str(event.payload_metadata.get("endpoint"))
    ]
    assert output_from_export
    assert all(event.payload_metadata["result"] == "ok" for event in output_from_export)


def test_missing_output_read_is_access_audited(tmp_path):
    def boom(_request):
        raise RuntimeError("model unavailable")

    private_key, public_key = generate_keypair()
    pipeline = Pipeline(
        PipelineServices(
            audit=AuditStore(tmp_path / "audit.sqlite"),
            content=ProtectedContentStore(tmp_path / "protected"),
            private_key=private_key,
            public_key=public_key,
            key_id="test-key",
        ),
        completer=boom,
    )
    client = TestClient(
        create_app(
            pipeline,
            auth=AuthConfig(
                accounts={ADMIN: Role.ADMIN, REVIEWER: Role.REVIEWER, INVESTIGATOR: Role.INVESTIGATOR}
            ),
        )
    )
    created = client.post("/transactions/run", json={}, headers=_headers())
    assert created.status_code == 200
    tx_id = created.json()["transaction"]["transaction_id"]
    response = client.get(f"/transactions/{tx_id}/output", headers=_headers(REVIEWER))
    assert response.status_code == 404
    access = client.app.state.pipeline.services.audit.list_access_events(tx_id)
    output_access = [event for event in access if event.payload_metadata.get("action") == "output"]
    assert output_access
    assert output_access[-1].payload_metadata["result"] == "missing"
    assert output_access[-1].payload_metadata["actor"] == "reviewer@curie.local"


def test_missing_transaction_read_is_access_audited(tmp_path):
    client = _client(tmp_path)
    missing_id = "missing-transaction-id"
    response = client.get(f"/transactions/{missing_id}", headers=_headers())
    assert response.status_code == 404
    access = client.app.state.pipeline.services.audit.list_access_events(missing_id)
    assert access
    assert access[-1].payload_metadata["actor"] == "admin@curie.local"
    assert access[-1].payload_metadata["result"] == "missing"
    assert access[-1].payload_metadata["action"] == "access"

