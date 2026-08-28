# Curie Audit Plane Architecture

## Purpose

Curie Audit Plane is a shared provenance boundary for clinical AI workflows. Its first prototype observes one synthetic FHIR-to-LLM transaction and makes the observable basis of that transaction reconstructable and tamper-evident.

The plane is not the FHIR server, the LLM, the clinical decision-support engine, or the human review authority. It records what those systems did, what artifacts they exchanged, what safeguards reported, and what the reviewer decided.

## First transaction flow

```text
Synthetic FHIR bundle / fixture repository
        |
        v
Input manifest + authorized resource read
        |
        v
Context builder
  - filtering and normalization
  - ordered context assembly
  - transformation manifests
        |
        +-----------------------> Protected clinical-content store
        |                           - context payload
        |                           - model request/response
        |                           - reviewer-modified text
        v
RAG retrieval and tool adapters
        |
        v
LLM adapter + model/prompt manifest
        |
        v
Structured output + rationale schema
        |
        v
Guardrail engine
        |
        v
Reviewer UI: ACCEPT / MODIFY / REJECT
        |
        v
Typed audit events
        |
        v
Canonical JSON -> SHA-256 event hashes -> transaction chain
        |
        v
Merkle batch root -> Ed25519 signature -> independent verifier
        |
        +-----------------------> Audit console
        |                           - timeline and tables
        |                           - JSON inspector
        |                           - Sankey with tabular fallback
        |                           - verification and replay views
        v
FHIR Provenance / AuditEvent projection
```

## Storage boundary

The protected clinical-content store contains payloads that may contain clinical information. The append-oriented audit store contains only the minimum metadata required to correlate, verify, and authorize reconstruction:

- event IDs, transaction IDs, sequence numbers, timestamps, and statuses;
- schemas, producer versions, model/prompt manifests, and policy versions;
- opaque protected-content references;
- evidence, tool, and output identifiers;
- content digests and integrity links;
- Merkle roots, signature metadata, and verification results.

Hashes and timestamps are still sensitive metadata. They are subject to access control, retention, and disclosure policy. A digest does not automatically make data anonymous or satisfy deletion obligations.

## Event sequence

The minimum successful sequence is:

1. `TRANSACTION_STARTED`
2. `FHIR_INPUT_MANIFESTED`
3. `TRANSFORMATION_RECORDED`
4. `CONTEXT_COMMITTED`
5. `EVIDENCE_RETRIEVED` (when retrieval is enabled)
6. `TOOL_CALLED` / `TOOL_COMPLETED` (when tools are enabled)
7. `MODEL_EXECUTED`
8. `STRUCTURED_OUTPUT_RECORDED`
9. `GUARDRAIL_EVALUATED`
10. `HUMAN_ACTION_RECORDED`
11. `INTEGRITY_PROOF_COMMITTED`
12. `TRANSACTION_COMPLETED`

Failed, blocked, incomplete, and tampered transactions remain visible with explicit status and missing-event information.

## Integrity model

Each event is canonically serialized before hashing. Events in one transaction link through `previous_event_hash` and a transaction root. Completed transaction roots are batched into a Merkle tree, and the batch root is signed with Ed25519. An independent verifier checks:

1. canonical serialization and each event hash;
2. sequence order and previous-hash links;
3. transaction root calculation;
4. Merkle inclusion proof;
5. signature validity and key identity;
6. required-event completeness and protected-content references.

This provides tamper evidence and provenance verification. It does not prove that the clinical output is correct, that the model is unbiased, or that a compromised signing key was honest before compromise.

## UI information architecture

The prototype console should have four primary surfaces:

| Surface | Purpose |
|---|---|
| Transaction overview | Show lifecycle status, integrity status, event counts, and missing/failed events. |
| Event explorer | Show a timeline, sortable event table, formatted/raw JSON, and linked detail tables. |
| Flow and evidence | Show recorded artifact flow through an interactive Sankey and evidence links. React Flow provenance graph is deferred. |
| Verification and replay | Show chain/Merkle/signature checks and compare original, modified, and replay outputs. |

The Sankey edge width must represent a declared measure such as artifact count, bytes, or tokens. It must be labeled as recorded flow, not causal influence. Edges link only consecutive handoff records between adjacent stages, not the union of every event on the source and target nodes. Every visual view needs a tabular fallback and text-based status labels.

## Curie integration boundaries

- `curie-fhir` is the first adapter and supplies the initial FHIR ingestion, context, retrieval, model, validation, and review workflow.
- `curie-prediction-pipeline` is a later adapter for deterministic event-time alerts, rule bundles, evidence IDs, and post-alert narratives. The audit plane must not move the LLM into the alert-firing path.
- `curie-gateway` is a later security/access adapter for tenant registration, token, certificate, and proxied FHIR request events.
- `personal-ai` may inform frontend interaction patterns, but its generic chat workflow is not the clinical audit contract.

## Implemented in this repository

- Event contract uses PRD dotted names (`transaction.started`). Architecture `TRANSACTION_STARTED` names are documentation aliases.
- Python modular monolith: SQLite audit store, SHA-256 content store, FastAPI, deterministic stub plus optional local OpenAI-compatible adapter (LM Studio), React/Vite console.
- Integrity: canonical JSON, event chain, RFC 6962-style Merkle promotion of unpaired nodes, Ed25519. Proof verification checks transaction IDs, roots, inclusion index, inclusion path, leaf, signature, and key identity.
- UI/export/replay access events are stored in a separate append-only access-audit stream keyed by `transaction_id`, hash-chained independently of the clinical transaction. Collection-level operations that have no transaction ID (transaction list and protected-content reads) use the documented global scope `access-scope:global`. Denied 401/403 attempts are recorded with the authenticated principal when it can be resolved, otherwise `anonymous` / `unauthenticated`. The clinical proof is not extended after `integrity.proof_committed`; appending to a sealed clinical chain is rejected.
- Prototype authorization is fail-closed: bearer tokens are generated locally by `curie-audit-plane setup` into gitignored `.env` (`CAP_ADMIN_TOKEN`, optional `CAP_REVIEWER_TOKEN` / `CAP_INVESTIGATOR_TOKEN`, and matching `VITE_CAP_AUTH_TOKEN`). `.env.example` keeps empty placeholders. Request bodies cannot set actor or role. Protected content is admin-only. Structured output is omitted from list, detail, run, and review responses. `GET /transactions/{id}/output` requires the separately audited `output` permission (`reviewer`, `admin`). Content references are resolved under the content root and digest-checked during verification.
- Research export includes de-identified clinical pipeline events and a verification summary. It excludes access-audit events, administrative events, raw payloads, reviewer comments, and direct identifiers. Clinical export requires `export` (`investigator`, `admin`). Export includes structured output only when the principal also has `output`; investigators receive `output: null`. When output is included, a second access-audit event with action `output` is recorded. Missing transaction reads are access-audited with result `missing` before the 404 response.
- Conceptual `curie-fhir` adapter via FHIR R4 synthetic fixtures; no runtime import of `curie-fhir`.
- Canonical event-to-stage mapping lives in `contracts/event-stages.json` and is shared by Sankey, console filters, and backend views.

## Deferred

Hosted cloud LLM providers, `curie-prediction-pipeline` and `curie-gateway` adapters, React Flow provenance graph, playback scrubber, SSE/live updates, production HSM/key rotation, and multi-tenant access control.

