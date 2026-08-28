# Curie Audit Plane Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement one synthetic FHIR-to-LLM transaction through guardrails, human ACCEPT/MODIFY/REJECT, cryptographic integrity proof, audit UI, and ARC/tamper evaluation.

**Architecture:** A Python 3.11 modular monolith (FastAPI + Pydantic + SQLite) observes a local synthetic FHIR-to-LLM workflow. Protected clinical payloads live in a content-addressed file store; the append-only audit store holds metadata, opaque references, schemas, and digests. A React/TypeScript Vite console consumes a typed view-model API. Integrity is a separate library: canonical JSON → SHA-256 → per-transaction hash chain → Merkle batch → Ed25519.

**Tech Stack:** Python 3.11, Pydantic v2, FastAPI, SQLite, cryptography (Ed25519), pytest; React 19, TypeScript, Vite, TanStack Query/Table, Apache ECharts. No blockchain, no hosted LLM in the first slice, no runtime import of `curie-fhir`.

**Spec:** `docs/PRD.md` (authoritative). Supporting: `CONTEXT.md`, `docs/architecture.md`, `docs/research-plan.md`.

## Global Constraints

- Synthetic FHIR R4 data only; never real patient data or production EHR access.
- Immutable audit store holds metadata, opaque references, schemas, and digests — never raw clinical payloads, prompts containing clinical content, or hidden chain-of-thought.
- Status families and event type strings are the PRD values; do not invent synonyms in APIs or UI labels.
- First adapter is conceptual `curie-fhir` (FHIR R4 resources, provenance envelopes, human review). Do not replace its ingestion, validation, or clinical-domain responsibilities. `curie-prediction-pipeline` and `curie-gateway` remain later adapters.
- Signing keys live in environment-configured paths; never commit keys or PHI.
- Browser verification uses only IronBee DevTools.

## Locked decisions (open PRD questions)

| Question | Ruling | Cost if wrong |
|---|---|---|
| Summary variant | Encounter-bounded longitudinal summary of one synthetic visit | Benchmark wording only |
| RAG corpus | One versioned external clinical-knowledge corpus plus patient-context evidence refs from the FHIR bundle | Extra evidence events; still one transaction |
| FHIR version | R4, matching `curie-fhir` | Mapping rework if a profile is mandated later |
| Guardrails | schema validation, evidence-ref completeness, uncertainty present, synthetic PHI-pattern scan | Can add rules without changing event shape |
| Modified output | New protected-content version linked to original AI output (`source_output_id`) | Matches FR-14 |
| Replay | Deterministic stub only; classify exact/equivalent/divergent by digest then canonical JSON | Hosted-model replay deferred |
| Immutable boundary | SQLite events table with no update/delete API + file protected store | Swap later without changing event schema |
| Signing | Ephemeral keys in tests; local gitignored keypair for demo via `CAP_SIGNING_KEY_PATH` | Not HSM; documented limitation |
| Event names | Persist PRD dotted names (`transaction.started`). Architecture `TRANSACTION_STARTED` is a documentation alias only | Callers that expected SCREAMING_SNAKE need the mapping table |

## Seams under test

1. `curie_audit_plane.integrity` — canonicalize, hash, chain, Merkle, sign, verify
2. `curie_audit_plane.store` — append audit events; put/get protected content by digest
3. `curie_audit_plane.pipeline` — `run_transaction(...)` / `record_human_action(...)` / `replay(...)`
4. HTTP API — transaction run, get, verify, review, export, replay
5. Evaluation — ARC and tamper-detection over fixture cases
6. Console view-model — statuses, timeline, table, JSON, Sankey metric, verification panel

## File map

```text
pyproject.toml
.env.example
src/curie_audit_plane/
  __init__.py
  config.py
  models/
    enums.py          # status families + EventType
    event.py          # AuditEventRecord
    manifests.py      # input/transform/model/evidence/tool/output/guardrail/human/batch
    report.py         # VerificationReport, transaction view model
  integrity/
    canonical.py
    hashing.py
    chain.py
    merkle.py
    signing.py
    verifier.py
  store/
    content.py        # protected content store
    audit.py          # append-only SQLite
  fhir/
    loader.py
    context.py
    projection.py     # Provenance + AuditEvent
  adapters/
    llm_stub.py
    retrieval.py
  guardrails/engine.py
  pipeline.py
  evaluation/
    fields.py
    benchmark.py
  api/app.py
fixtures/
  fhir/synthetic-encounter-bundle.json
  corpus/clinical-knowledge.v1.json
console/                  # Vite React TS app
tests/
  unit/
  integration/
  evaluation/
docs/adr/0001-prototype-stack-and-event-contract.md
```

## Shared interfaces

```python
SCHEMA_VERSION = "1.0.0"
PRODUCER_VERSION = "0.1.0"
GENESIS_HASH = "0" * 64

class EventType(StrEnum):
    TRANSACTION_STARTED = "transaction.started"
    INPUT_MANIFEST_CREATED = "input.manifest.created"
    TRANSFORMATION_APPLIED = "transformation.applied"
    CONTEXT_MANIFEST_CREATED = "context.manifest.created"
    RETRIEVAL_COMPLETED = "retrieval.completed"
    TOOL_CALLED = "tool.called"
    TOOL_COMPLETED = "tool.completed"
    MODEL_REQUESTED = "model.requested"
    MODEL_RESPONDED = "model.responded"
    STRUCTURED_OUTPUT_VALIDATED = "structured_output.validated"
    GUARDRAIL_COMPLETED = "guardrail.completed"
    HUMAN_ACTION_RECORDED = "human.action_recorded"
    TRANSACTION_COMPLETED = "transaction.completed"
    TRANSACTION_FAILED = "transaction.failed"
    INTEGRITY_PROOF_COMMITTED = "integrity.proof_committed"
    UI_ACCESS_RECORDED = "ui.access_recorded"
    EXPORT_RECORDED = "export.recorded"

REQUIRED_SUCCESS_EVENTS = (
    EventType.TRANSACTION_STARTED,
    EventType.INPUT_MANIFEST_CREATED,
    EventType.TRANSFORMATION_APPLIED,
    EventType.CONTEXT_MANIFEST_CREATED,
    EventType.MODEL_REQUESTED,
    EventType.MODEL_RESPONDED,
    EventType.STRUCTURED_OUTPUT_VALIDATED,
    EventType.GUARDRAIL_COMPLETED,
    EventType.HUMAN_ACTION_RECORDED,
    EventType.INTEGRITY_PROOF_COMMITTED,
    EventType.TRANSACTION_COMPLETED,
)

def canonicalize(value: object) -> bytes: ...
def sha256_hex(data: bytes) -> str: ...
def hash_event(event: dict) -> str: ...  # event_hash field omitted
def link_chain(events: list[AuditEventRecord]) -> list[AuditEventRecord]: ...
def merkle_root(leaves: Sequence[str]) -> str: ...
def merkle_proof(leaves: Sequence[str], index: int) -> MerkleProof: ...
def verify_merkle_proof(leaf: str, proof: MerkleProof, root: str) -> bool: ...
def generate_keypair() -> tuple[bytes, bytes]: ...  # private, public raw
def sign_hex(message_hex: str, private_key: bytes) -> str: ...
def verify_signature(message_hex: str, signature_hex: str, public_key: bytes) -> bool: ...
def verify_transaction(events, batch: IntegrityBatch | None, public_key: bytes) -> VerificationReport: ...

class ProtectedContentStore:
    def put(self, payload: bytes, media_type: str) -> ContentRef: ...  # ref is "sha256:<hex>"
    def get(self, ref: str) -> bytes: ...

class AuditStore:
    def create_transaction(self, tx: Transaction) -> None: ...
    def append_event(self, event: AuditEventRecord) -> None: ...  # raises if mutate/delete attempted
    def list_events(self, transaction_id: str) -> list[AuditEventRecord]: ...
    def get_transaction(self, transaction_id: str) -> Transaction: ...

class StructuredRationale(BaseModel):
    summary: str
    findings: list[Finding]  # text + evidence_refs
    evidence_references: list[str]
    uncertainty: str
    assumptions: list[str]
    missing_data: list[str]
    follow_up_questions: list[str]
    # no chain_of_thought / hidden_reasoning / thinking fields

def run_transaction(*, fixture_id: str, human_action: HumanActionStatus | None = None, ...) -> TransactionResult: ...
def record_human_action(transaction_id: str, action: HumanActionStatus, ...) -> TransactionResult: ...
def replay_transaction(transaction_id: str) -> ReplayResult: ...  # exact | equivalent | divergent
```

Sankey metric default: `artifact_count`. UI caption: "Recorded artifact flow (edge width = artifact count). Width does not imply causal influence."

---

### Task 1: Repository scaffold and ADR

**Files:**
- Create: `pyproject.toml`, `src/curie_audit_plane/__init__.py`, `src/curie_audit_plane/config.py`, `.env.example`, `docs/adr/0001-prototype-stack-and-event-contract.md`
- Modify: `.gitignore`, `README.md`

- [ ] **Step 1:** Add ignore rules for `data/`, `*.db`, `console/node_modules/`, `console/dist/`, `.superpowers/`.
- [ ] **Step 2:** Add `pyproject.toml` with hatchling, pytest, ruff, pytest-cov, fastapi, pydantic, cryptography, sqlmodel.
- [ ] **Step 3:** Write ADR locking stack, PRD event names, data/proof split, curie-fhir conceptual adapter, deferred prediction-pipeline/gateway.
- [ ] **Step 4:** `.env.example` with `CAP_DATA_DIR`, `CAP_SIGNING_KEY_PATH`, `CAP_VERIFYING_KEY_PATH` only.

### Task 2: Status and event contracts

**Files:**
- Create: `src/curie_audit_plane/models/enums.py`, `src/curie_audit_plane/models/event.py`, `tests/unit/test_event_contract.py`

- [ ] **Step 1: Write the failing test**

```python
def test_event_types_match_prd_dotted_names():
    assert EventType.TRANSACTION_STARTED == "transaction.started"
    assert "chain_of_thought" not in StructuredRationale.model_fields
    assert "hidden_reasoning" not in StructuredRationale.model_fields

def test_transaction_statuses_are_prd_family():
    assert {s.value for s in TransactionStatus} == {
        "STARTED", "RUNNING", "WAITING_FOR_REVIEW", "COMPLETED",
        "FAILED", "BLOCKED", "INCOMPLETE", "TAMPERED",
    }
```

- [ ] **Step 2:** Run `pytest tests/unit/test_event_contract.py -v` — expected RED (import missing).
- [ ] **Step 3:** Implement enums and `AuditEventRecord` / `StructuredRationale`.
- [ ] **Step 4:** Re-run test — GREEN.

### Task 3: Canonical JSON and event hashing

**Files:**
- Create: `src/curie_audit_plane/integrity/canonical.py`, `src/curie_audit_plane/integrity/hashing.py`, `tests/unit/test_canonical_hash.py`

- [ ] **Step 1: Write the failing test**

```python
def test_canonicalize_sorts_keys_and_drops_whitespace():
    assert canonicalize({"b": 1, "a": 2}) == b'{"a":2,"b":1}'

def test_hash_event_ignores_event_hash_field():
    event = {"event_id": "e1", "event_hash": "deadbeef", "n": 1}
    assert hash_event(event) == hash_event({"event_id": "e1", "n": 1})
    assert hash_event(event) == sha256_hex(canonicalize({"event_id": "e1", "n": 1}))
```

- [ ] **Step 2:** Prove RED, implement, prove GREEN.
- [ ] **Step 3:** Independent-verifier test: two implementations of sort+dump produce the same SHA-256.

### Task 4: Hash chaining

**Files:**
- Create: `src/curie_audit_plane/integrity/chain.py`, `tests/unit/test_chain.py`

```python
def test_first_event_links_to_genesis():
    events = link_chain([make_event(seq=0), make_event(seq=1)])
    assert events[0].previous_event_hash == GENESIS_HASH
    assert events[1].previous_event_hash == events[0].event_hash

def test_reordering_breaks_chain_verification():
    chained = link_chain([make_event(seq=0), make_event(seq=1), make_event(seq=2)])
    reordered = [chained[0], chained[2], chained[1]]
    report = verify_chain(reordered)
    assert report.ok is False
```

### Task 5: Merkle batching and Ed25519 signatures

**Files:**
- Create: `src/curie_audit_plane/integrity/merkle.py`, `src/curie_audit_plane/integrity/signing.py`, `tests/unit/test_merkle_signing.py`

```python
def test_inclusion_proof_verifies_and_detects_wrong_leaf():
    leaves = [sha256_hex(b"a"), sha256_hex(b"b"), sha256_hex(b"c")]
    root = merkle_root(leaves)
    proof = merkle_proof(leaves, 1)
    assert verify_merkle_proof(leaves[1], proof, root)
    assert not verify_merkle_proof(leaves[0], proof, root)

def test_signature_roundtrip_and_wrong_key_fails():
    priv, pub = generate_keypair()
    other_priv, other_pub = generate_keypair()
    sig = sign_hex(root, priv)
    assert verify_signature(root, sig, pub)
    assert not verify_signature(root, sig, other_pub)
```

Merkle: RFC 6962 style — unpaired node promoted, not duplicated. Leaf hash is the transaction root (already SHA-256 hex of the last event hash / dedicated root field).

### Task 6: Independent verifier and tamper suite

**Files:**
- Create: `src/curie_audit_plane/integrity/verifier.py`, `src/curie_audit_plane/models/report.py`, `tests/unit/test_verifier_tamper.py`

Tamper cases that must yield `VerificationStatus.TAMPERED` or `FAILED` (never silent `COMPLETED`):

1. Mutated model version in payload metadata
2. Deleted guardrail event
3. Reordered events
4. Broken `previous_event_hash`
5. Wrong protected-content digest
6. Invalid Merkle proof
7. Substituted signature / wrong public key

Clean fixture must yield `VERIFIED` with false-tamper = 0.

Missing required events on an otherwise intact chain yield `INCOMPLETE`, not `VERIFIED`.

### Task 7: Protected content store and redaction

**Files:**
- Create: `src/curie_audit_plane/store/content.py`, `tests/unit/test_content_store.py`

```python
def test_put_returns_sha256_ref_and_get_roundtrips():
    store = ProtectedContentStore(tmp_path)
    ref = store.put(b'{"resourceType":"Patient"}', "application/fhir+json")
    assert ref.startswith("sha256:")
    assert store.get(ref) == b'{"resourceType":"Patient"}'

def test_audit_event_payload_metadata_rejects_clinical_keys():
    with pytest.raises(ValueError):
        AuditEventRecord(..., payload_metadata={"resource": {"resourceType": "Patient"}})
```

Forbidden metadata keys: `resource`, `prompt`, `context`, `note`, `chain_of_thought`, `hidden_reasoning`.

### Task 8: Append-only audit store

**Files:**
- Create: `src/curie_audit_plane/store/audit.py`, `tests/unit/test_audit_store.py`

```python
def test_append_then_list_preserves_order():
    ...

def test_store_has_no_update_or_delete_api():
    assert not hasattr(AuditStore, "update_event")
    assert not hasattr(AuditStore, "delete_event")
```

### Task 9: Synthetic FHIR fixture and input manifest

**Files:**
- Create: `fixtures/fhir/synthetic-encounter-bundle.json`, `src/curie_audit_plane/fhir/loader.py`, `tests/unit/test_input_manifest.py`

Bundle must include Patient, Encounter, Observation, Condition, MedicationRequest, DiagnosticReport with fake identifiers (`TEST-00001`, `Jane Test`). README in fixtures stating synthetic/non-PHI.

Input manifest records resourceType, id, source `curie-fhir-fixture`, version/time, selection reason, content ref, SHA-256 digest.

### Task 10: Transformations and context builder

**Files:**
- Create: `src/curie_audit_plane/fhir/context.py`, `tests/unit/test_context_builder.py`

Named operations: `filter_resource_types`, `normalize_codes`, `order_context_window`. Each records operation id, code version, parameter digest, input refs, output ref, output digest. Re-running an operation on the same inputs must reproduce the output digest.

### Task 11: Retrieval evidence and tool records

**Files:**
- Create: `fixtures/corpus/clinical-knowledge.v1.json`, `src/curie_audit_plane/adapters/retrieval.py`, `tests/unit/test_retrieval_and_tools.py`

Corpus chunks have stable IDs, version `clinical-knowledge.v1`, digest. Retrieval event includes corpus ID, chunk ID, rank/score, URI/ref, digest. One deterministic tool `knowledge.lookup` records sanitized args (chunk id only), result ref/digest, status, sequence.

### Task 12: Deterministic LLM stub and structured output

**Files:**
- Create: `src/curie_audit_plane/adapters/llm_stub.py`, `src/curie_audit_plane/models/manifests.py`, `tests/unit/test_llm_stub.py`

Stub output is a pure function of `(model_id, prompt_version, context_digest, corpus_version)`. Two different prompt versions produce distinguishable model manifests. Invalid structured output is rejected (`EventStatus.FAILED`) and never reaches human review. Schema contains findings, evidence_references, uncertainty, assumptions, missing_data, follow_up_questions; tests assert no hidden-reasoning field.

### Task 13: Guardrails

**Files:**
- Create: `src/curie_audit_plane/guardrails/engine.py`, `tests/unit/test_guardrails.py`

Rules with id/version:

| rule_id | PASS | WARN | BLOCK | ERROR |
|---|---|---|---|---|
| `schema.v1` | valid output | — | — | malformed JSON |
| `evidence_refs.v1` | all findings cited | some findings uncited | zero citations when findings exist | — |
| `uncertainty.v1` | present | empty string | — | missing field |
| `phi_scan.v1` | no SSN/MRN pattern beyond fixture ids | fixture MRN present in output text | — | scanner exception |

BLOCK prevents `COMPLETED` without explicit override recorded as human action comment + policy version. ACCEPT of a blocked transaction without override must fail.

### Task 14: Human ACCEPT / MODIFY / REJECT

**Files:**
- Create: tests in `tests/unit/test_human_action.py`; implementation in `pipeline.py`

Each action records actor, role, timestamp, comment, source output id, final-output digest. MODIFY stores a new protected payload linked to the original. A completed demo transaction has exactly one terminal human disposition.

### Task 15: Transaction orchestrator

**Files:**
- Create: `src/curie_audit_plane/pipeline.py`, `tests/integration/test_full_transaction.py`

`run_transaction` emits the PRD event sequence, stores clinical payloads only in the protected store, commits integrity proof, and returns `INCOMPLETE` if a required event is missing rather than `COMPLETED`. Include a `curie-fhir` adapter note: input source_system `curie-fhir-fixture`; do not call curie-fhir runtime.

### Task 16: FHIR Provenance and AuditEvent projections

**Files:**
- Create: `src/curie_audit_plane/fhir/projection.py`, `tests/unit/test_fhir_projection.py`

Provenance target = structured output ref; agents = AI service + reviewer; entities = source FHIR refs + model/prompt manifest refs. AuditEvent subtypes for access, model execution, retrieval, guardrail, human review, export, verification. Mapping rules documented in `docs/fhir-mapping.md`. Validate required FHIR R4 fields (`resourceType`, `type`/`agent`/`recorded` for Provenance; `type`/`recorded`/`agent` for AuditEvent).

### Task 17: FastAPI

**Files:**
- Create: `src/curie_audit_plane/api/app.py`, `tests/integration/test_api.py`

| Method | Path | Behavior |
|---|---|---|
| POST | `/transactions/run` | Run synthetic fixture |
| GET | `/transactions` | List |
| GET | `/transactions/{id}` | Overview view-model |
| GET | `/transactions/{id}/events` | Events + formatted JSON |
| POST | `/transactions/{id}/verify` | Verification panel payload |
| POST | `/transactions/{id}/review` | ACCEPT/MODIFY/REJECT |
| POST | `/transactions/{id}/replay` | Stub replay comparison |
| GET | `/transactions/{id}/export` | Audit package + FHIR projection |
| GET | `/transactions/{id}/sankey` | Nodes/edges with `metric=artifact_count` |
| GET | `/content/{digest}` | Protected payload (prototype local) |

Validate all request bodies with Pydantic. UI access and export append `ui.access_recorded` / `export.recorded`.

### Task 18: Evaluation — ARC and tamper detection

**Files:**
- Create: `src/curie_audit_plane/evaluation/fields.py`, `src/curie_audit_plane/evaluation/benchmark.py`, `tests/evaluation/test_benchmark.py`

Required provenance fields listed explicitly. ARC = reconstructed+verified / total required. Clean fixture ≥ 95% with no silent omissions. Tamper suite detection rate 100%; false tamper 0%. CLI: `curie-audit-plane evaluate`.

### Task 19: Audit console

**Files:**
- Create: `console/` Vite React TS app

P0 surfaces: transaction overview; chronological timeline by stage; sortable event table (sequence, timestamp, type, actor, status, payload ref, hash verification); formatted+raw JSON with copy/download; detail tables; status badges+filters with text (not color-only); evidence/related-record links; structured rationale separate from raw text; verification panel (chain, Merkle, signature, key ID, time, scope); replay comparison (original / modified / replay + digests); interactive Sankey with declared artifact-count metric, click-to-filter, keyboard focus, reset, text status overlay, tabular fallback.

Visual direction: clinical operations console — cool paper-chart canvas `#e7edf2`, ink `#1b2430`, single verification seal accent `#0f6e6e`, IBM Plex Sans + IBM Plex Mono. No 3D, no decorative dashboards.

Unit tests with Vitest for view-model filters, Sankey metric labeling, and status text. Browser verification via IronBee DevTools against the running app.

### Task 20: Documentation, coverage, handoff

**Files:**
- Modify: `README.md`, `docs/architecture.md` (implemented vs deferred)
- Create: `docs/fhir-mapping.md`, `docs/testing/prototype.tdd.md`

Record implemented vs deferred (`curie-prediction-pipeline`, `curie-gateway`, hosted LLM, React Flow graph, playback scrubber, global search, production key management). Run pytest with coverage, console unit tests, focused API integration, and browser verification. Final report: files changed, commands, results, unresolved risks.

## Parallelization gate

Tasks 1–8 are sequential (shared contract). After Task 8, Tasks 9–12 may proceed in parallel if they consume only the frozen models/store/integrity interfaces. Tasks 13–17 depend on the pipeline. Task 19 may start against mocked API fixtures once Task 17's view-model JSON is frozen.

## Out of scope (do not build)

- Hosted LLM provider, blockchain, multi-tenant, UDAP/TEFCA, production EHR, alert-path LLM, React Flow provenance graph, playback scrubber, SSE live updates, Monaco editor, Docker compose unless needed for a failing acceptance check.
