# Product Requirements Document

## Curie Audit Plane / Clinical AI Flight Recorder

**Document status:** First prototype PRD  
**Date:** 2026-08-27  
**Project name:** Curie Audit Plane  
**Repository identifier:** `curie-audit-plane`  
**Canonical repository:** [github.com/sreeram843/curie-audit-plane](https://github.com/sreeram843/curie-audit-plane)  
**Audience:** Research collaborators, clinical informatics reviewers, platform engineers, security/compliance stakeholders, and potential pilot customers  
**Primary decision:** Build a narrow, verifiable provenance prototype around one synthetic-data FHIR-to-LLM transaction before expanding into a general healthcare audit platform.
**Primary publication target:** IEEE Journal of Biomedical and Health Informatics (J-BHI); IEEE Access and IEEE EMBC/EMBS remain fallback or companion routes.

## 1. Executive summary

Healthcare organizations need to determine what a clinical AI system saw, how that information was transformed, which model and prompt produced an output, what evidence and tools were used, which safeguards ran, and what a human ultimately did. Ordinary application logs are often incomplete, mutable, difficult to correlate, and not designed for clinical provenance.

Curie Audit Plane (CAP), also called the Clinical AI Flight Recorder, is a provenance layer around an AI workflow. It separates clinical data from audit proof: patient content remains in an authorized clinical datastore, while the audit plane records manifests, references, structured outputs, event metadata, and cryptographic integrity proofs. The prototype must support independent reconstruction of a transaction without exposing hidden chain-of-thought or placing raw PHI in an immutable log.

The first release will demonstrate one end-to-end workflow:

> Given a synthetic FHIR patient bundle, assemble a bounded context, optionally retrieve supporting clinical knowledge, call an LLM, produce a structured clinical summary with evidence references and uncertainty, run guardrails, record a human ACCEPT/MODIFY/REJECT action, and verify the complete provenance record.

The prototype is a research instrument, not a clinical product. Its commercial direction is a deployable audit and governance service for healthcare AI vendors and provider organizations.

**Storage rule:** Any payload that may contain clinical content—including the assembled context, model request/response, structured output, reviewer-modified text, and tool arguments/results—is stored only in the authorized clinical-content store or fixture repository. The immutable audit store holds event metadata, opaque references, schemas, and cryptographic digests needed to verify and reconstruct the transaction under authorization.

## 2. Problem and opportunity

### Current problem

When an AI-generated clinical output is questioned, teams commonly lack a reliable answer to one or more of these questions:

- Which exact FHIR resources and fields were available to the AI?
- What filtering, normalization, de-identification, or summarization occurred?
- Which prompt, model version, endpoint, and runtime settings were used?
- Which retrieved passages, tools, or external services contributed?
- Did a safety or policy check fail, warn, or pass?
- Did a clinician accept, modify, or reject the result?
- Can an investigator prove that the audit record was not altered after the event?

This creates operational, safety, research, and governance risk. It also makes it hard to compare model versions or reproduce failures.

### Opportunity

Provide a vendor-neutral provenance layer that makes an AI transaction reconstructable and tamper-evident while keeping clinical content under existing access controls. The differentiated research claim is not “the system exposes model thoughts.” It is:

> A clinical AI decision can be independently reconstructed from a complete, cryptographically verifiable record of inputs, transformations, execution configuration, evidence, safeguards, and human disposition.

## 3. Goals

### Prototype goals

1. Capture a complete provenance record for one bounded FHIR-to-LLM transaction.
2. Keep raw patient data out of the immutable audit event store.
3. Make every material input, transformation, model setting, evidence item, tool call, guardrail result, and human action addressable.
4. Verify record integrity using canonical JSON hashing, per-transaction hash chaining, batch Merkle roots, and digital signatures.
5. Reconstruct a human-readable transaction timeline and a machine-verifiable audit package.
6. Measure reconstruction completeness, tamper detection, replay fidelity, latency, and storage/compute overhead.
7. Create a credible foundation for a research paper and a later hospital/vendor pilot.

### Product-direction goals

1. Offer an integration boundary that can sit beside FHIR servers, AI gateways, RAG services, and clinical applications.
2. Support organization-controlled retention, access, and key management.
3. Map operational events to FHIR `Provenance` and `AuditEvent` resources.
4. Enable governance teams to investigate a transaction without requiring model internals or vendor-specific logs.

## 4. Non-goals and guardrails

The initial implementation will not:

- Make autonomous diagnoses, prescriptions, triage decisions, or treatment changes.
- Store raw PHI, full clinical notes, prompts containing PHI, or hidden chain-of-thought in an immutable ledger.
- Claim that a hash is anonymous or automatically satisfies deletion, privacy, or healthcare regulatory obligations.
- Reconstruct hidden model reasoning. It will record structured rationale and evidence links supplied as an auditable output contract.
- Guarantee bit-for-bit replay of a hosted, nondeterministic model. It will reconstruct the input/configuration and report output divergence when exact replay is unavailable.
- Build a blockchain, cryptocurrency, public consensus network, or decentralized identity system.
- Become a full SIEM, enterprise data lake, clinical decision support engine, or model training platform.
- Integrate with live production EHRs during the first prototype.
- Establish regulatory clearance, clinical efficacy, or legal compliance. Those are later workstreams requiring domain review.

## 5. Initial use case and prototype boundary

### Use case

**AI-assisted longitudinal clinical summary for clinician review.**

The user selects a synthetic patient encounter or bundle. CAP assembles a bounded context from FHIR resources such as Patient, Encounter, Observation, Condition, MedicationRequest, and DiagnosticReport. An optional retrieval step finds relevant passages from a versioned clinical knowledge corpus. The LLM returns a structured summary containing key findings, evidence references, uncertainty, missing information, and suggested follow-up questions. Guardrails run, and a reviewer records ACCEPT, MODIFY, or REJECT.

### Transaction boundary

One transaction begins when the context builder receives the requested FHIR resource set and ends when the human disposition and final integrity proof are committed. Every event belongs to a `transaction_id` and has a monotonic `sequence_number` within that transaction.

### Prototype environment

- Synthetic FHIR bundles only.
- Local or controlled development deployment.
- One FHIR server or fixture repository.
- One LLM provider adapter plus a stub adapter for deterministic tests.
- One versioned retrieval corpus.
- One guardrail runner with a small, explicit rule set.
- One reviewer web UI.
- One append-oriented audit store and one clinical-content store or fixture repository.

## 6. Users and user stories

### Primary users

| User | Need | Prototype outcome |
|---|---|---|
| Clinical reviewer | Understand and disposition an AI summary | Sees evidence-linked output, warnings, and ACCEPT/MODIFY/REJECT controls |
| AI/platform engineer | Diagnose a bad or surprising output | Reconstructs exact inputs, transformations, configuration, tools, and guardrails |
| Researcher/evaluator | Compare runs and quantify auditability | Exports structured records and computes metrics |
| Compliance/security investigator | Verify provenance and detect tampering | Runs integrity verification and reviews access/event history |
| Product/operator owner | Decide whether the system is safe to pilot | Sees completeness, failures, latency, and operational health |

### User stories

- As a clinical reviewer, I want to see why a summary was produced in terms of evidence and uncertainty, so that I can make an informed disposition.
- As a clinical reviewer, I want my ACCEPT, MODIFY, or REJECT action recorded with the final text and reason, so that the human-AI handoff is auditable.
- As an engineer, I want to replay the same transaction inputs and configuration, so that I can investigate a regression.
- As a researcher, I want to calculate Audit Reconstruction Completeness across runs, so that I can evaluate whether the audit plane captures what it claims.
- As an investigator, I want to detect a modified event or missing event, so that the audit record is not trusted merely because it exists.
- As a governance owner, I want to inspect a transaction without exposing more patient data than necessary, so that investigation follows least privilege.
- As a future integrator, I want FHIR-native provenance mappings and an API boundary, so that I can connect the plane to an existing clinical workflow.

## 7. Product principles

1. **Provenance over pseudo-explanation.** Record observable inputs, outputs, evidence, configuration, safeguards, and actions; do not claim access to hidden reasoning.
2. **Data/proof separation.** Keep clinical content in an authorized store and commit only the minimum necessary content references and digests to the audit store.
3. **Reconstructability is testable.** Every required field has an owner, schema, digest, and reconstruction test.
4. **Human accountability is first-class.** The clinical reviewer’s action is part of the transaction, not an annotation added later.
5. **Fail closed on missing provenance.** A transaction with incomplete required evidence is visibly marked incomplete and is not presented as fully auditable.
6. **Portable standards at the boundary.** Use FHIR `Provenance` and `AuditEvent` mappings, canonical JSON, and documented APIs.

## 8. Functional requirements

Priority levels: **P0** is required for the research prototype; **P1** is desirable for a credible demo or paper; **P2** is product-direction work.

### Transaction capture

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-01 | P0 | Create a unique `transaction_id` and immutable event sequence for each run. | A run can be loaded by ID and its ordered event list is complete. |
| FR-02 | P0 | Record the requested FHIR resources, stable resource IDs, versions/timestamps where available, source location, and content digest in an input manifest. | The manifest identifies every input used by the context builder. |
| FR-03 | P0 | Record transformations as ordered, named operations with parameters, code/version identity, input references, output references, and digests. | A reviewer can explain how source resources became model context. |
| FR-04 | P0 | Record the exact context payload or a protected content reference sufficient for authorized replay, plus its digest and serialization format. | Recomputed digest matches the committed manifest. |
| FR-05 | P0 | Capture model, endpoint, prompt/template, decoding parameters, tool policy, runtime, and execution timestamps in a model manifest. | Two runs with different configurations produce distinguishable manifests. |
| FR-06 | P0 | Capture request/response references and digests, status, token/usage metadata when available, and error details without writing clinical payloads or secrets to the immutable audit record. | Failed model calls remain auditable. |

### Evidence, tools, and rationale

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-07 | P0 | Record retrieved evidence items with corpus ID, document/chunk ID, version, retrieval timestamp, rank/score if available, URI/reference, and digest. | The UI can show which evidence supported the output. |
| FR-08 | P0 | Record tool calls, including tool name/version, sanitized arguments or protected argument reference, result reference/digest, status, and sequence. | Tool activity is visible in the timeline and linked to the output. |
| FR-09 | P0 | Require a structured output schema with summary, findings, evidence references, uncertainty, assumptions, missing data, and follow-up questions; keep the payload in the protected content store and commit only its reference/digest to the immutable audit record. | Invalid output is rejected or marked failed before human review. |
| FR-10 | P0 | Store structured rationale only; never label or persist hidden chain-of-thought as an audit artifact. | Schema and tests contain no hidden-reasoning field. |

### Guardrails and human review

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-11 | P0 | Run versioned guardrails over input/context, retrieved evidence, output schema, and selected safety policies. | Each check has rule ID/version, input reference, result, severity, and timestamp. |
| FR-12 | P0 | Make blocking guardrail failures prevent automatic completion and visibly explain the required reviewer action. | A blocked output cannot be marked accepted without an explicit override policy. |
| FR-13 | P0 | Provide ACCEPT, MODIFY, and REJECT actions with actor, role, timestamp, comment, and final-output digest. | Each completed transaction has exactly one terminal human disposition in the demo workflow. |
| FR-14 | P1 | Support modified output as a new version linked to the original AI output. | The UI distinguishes AI output from human-modified final output. |

### Integrity, standards, and export

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-15 | P0 | Canonicalize each event and compute a SHA-256 content hash. | Independent verifier recomputes every event hash. |
| FR-16 | P0 | Chain events using `previous_event_hash` and a transaction root. | Reordering, deletion, or mutation breaks verification. |
| FR-17 | P0 | Batch completed transaction roots into a Merkle tree and sign the Merkle root with an Ed25519 key. | Verifier validates inclusion proof and signature with the published public key. |
| FR-18 | P0 | Treat audit records and hashes as sensitive metadata subject to access, retention, and deletion policy. | Documentation does not promise that hashes are anonymous or erasable. |
| FR-19 | P0 | Generate FHIR `Provenance` and `AuditEvent` mappings for the transaction and expose an exportable audit package. | Export validates against the selected FHIR profile or documented mapping rules. |
| FR-20 | P1 | Provide a machine-readable verification report with pass/fail status, missing required events, hash failures, and signature status. | A user can verify a package without the main UI. |

### Replay and audit UI

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-21 | P0 | Display a transaction timeline from input acquisition through human disposition. | A new user can identify every major stage in one screen. |
| FR-22 | P0 | Provide detail views for input manifest, transformations, model/prompt manifest, evidence, tools, guardrails, and human action. | Every P0 event is reachable from the transaction page. |
| FR-23 | P0 | Provide an integrity verification action and show the exact scope verified. | The UI distinguishes verified, incomplete, and tampered states. |
| FR-24 | P1 | Provide replay that reuses a captured context/configuration or a deterministic stub and compares the new output with the original. | Replay reports exact, equivalent, or divergent result with reasons. |
| FR-25 | P1 | Export a de-identified research record separate from an authorized clinical-content package. | Researchers can evaluate provenance without receiving raw clinical content. |

### Audit console and data views

The UI is a core prototype deliverable. It must make the transaction understandable to a reviewer who did not build the system and must expose structured data for technical investigation.

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-26 | P0 | Provide a transaction overview with transaction ID, purpose, subject reference, start/end time, current status, integrity status, event count, and missing/failed-event count. | A reviewer can determine whether a transaction is complete and trustworthy without opening details. |
| FR-27 | P0 | Provide a chronological event timeline grouped by workflow stage: inputs, transformations, retrieval, tools, model, output, guardrails, human review, and proof. | The full lifecycle is visible and each stage links to its event details. |
| FR-28 | P0 | Provide an event table with sortable columns for sequence, timestamp, event type, actor/service, status, payload reference, and hash verification. | A user can sort, scan, and identify failed or missing events. |
| FR-29 | P0 | Provide both formatted JSON and raw JSON views for every event and manifest, with schema version, digest, and copy/download actions. | A technical user can inspect the exact machine-readable record without database access. |
| FR-30 | P0 | Provide detail tables for FHIR inputs, transformations, model/prompt configuration, retrieved evidence, tool calls, guardrails, and human actions. | Each requested audit dimension has a dedicated, readable view. |
| FR-31 | P0 | Provide status badges and filters for transaction, event, guardrail, verification, and human-action statuses. | Status can be understood without relying on color alone, and filters return the expected records. |
| FR-32 | P0 | Link related records across views, such as an output claim to evidence, a tool call to its result, and a human modification to the original AI output. | A reviewer can follow provenance relationships without manually matching IDs. |
| FR-33 | P0 | Show structured rationale, uncertainty, assumptions, missing data, and evidence references separately from raw output text. | The UI does not present hidden chain-of-thought or an undifferentiated block of prose. |
| FR-34 | P0 | Provide a visible verification panel showing chain, Merkle proof, signature, key ID, verification time, and verification scope. | Users can distinguish verified, incomplete, failed, and tampered states. |
| FR-35 | P1 | Provide global search and filters by transaction ID, subject reference, event type, status, actor, model version, prompt version, date, and guardrail severity. | An investigator can find a target transaction without knowing its exact ID. |
| FR-36 | P1 | Provide side-by-side comparison of AI output, modified output, replay output, and their digests. | Differences are visible and linked to the corresponding events. |
| FR-37 | P1 | Provide a downloadable audit package and a separate de-identified research package from the UI. | Exports preserve verification metadata and respect the content-access boundary. |

### Interactive visualizations

The visual layer should help a reviewer answer “what flowed where, what failed, and what can I inspect next?” Every visualization is a navigation surface into the authoritative event records, not a substitute for them.

| ID | Priority | Requirement | Acceptance signal |
|---|---|---|---|
| FR-38 | P0 | Provide an interactive Sankey view of recorded artifact flow: FHIR inputs → transformations → context → RAG evidence/tools → model execution → structured output → guardrails → human action → integrity proof. | A reviewer can see the complete path and click any node or edge to open the linked records. |
| FR-39 | P0 | Make Sankey edge width represent a declared measurable quantity such as artifact count, bytes, or tokens; default to artifact count. Label the view as recorded flow, not causal influence. | The chart never implies that visual width proves why the model made a decision. |
| FR-40 | P0 | Support hover, click-to-focus, click-to-filter, keyboard focus, zoom/pan where needed, and a reset view for Sankey nodes and edges. | Selecting a node filters the event table and JSON panel to the same provenance slice. |
| FR-41 | P0 | Provide a status overlay for the Sankey and timeline using text labels and accessible patterns for PASS, WARN, BLOCK, FAILED, MISSING, and TAMPERED. | A user can identify failure paths when color is removed or viewed with color-vision deficiency. |
| FR-42 | P1 | Provide an interactive provenance graph for many-to-many relationships among inputs, transformations, evidence, tools, outputs, guardrails, and human actions. | Users can expand/collapse related nodes and jump to the corresponding event details. |
| FR-43 | P1 | Provide a playback mode with a timeline scrubber that reveals events in sequence and pauses on failures, guardrail blocks, human actions, or verification failures. | Playback can be paused, resumed, reset, and reduced/disabled for motion-sensitive users. |
| FR-44 | P1 | Provide compact trend views across transactions for status counts, ARC, tamper detections, guardrail outcomes, latency, and model/prompt versions. | Researchers can compare runs without confusing aggregate metrics with a single transaction’s evidence. |

### Recommended UI technology pipeline

For the prototype, use a React and TypeScript single-page application with a typed API view-model layer. Recommended libraries are:

- **Apache ECharts:** Sankey, timeline, status trends, and other quantitative charts.
- **React Flow:** expandable node-edge provenance graph with custom audit nodes.
- **TanStack Table + TanStack Virtual:** sortable/filterable event tables, server-side pagination, and virtualization for large event sets.
- **Monaco Editor or CodeMirror:** formatted/raw JSON, search, copy, and side-by-side JSON diff.
- **TanStack Query:** server-state fetching, caching, pagination, and mutation state.
- **Server-sent events (SSE):** live transaction progress and status updates during a running workflow; use WebSockets only if bidirectional interaction becomes necessary.
- **Accessible component layer:** Radix UI or an equivalent keyboard-first component system, with a restrained clinical-operations visual language.

The UI rendering pipeline should be:

```text
Audit API / SSE
      ↓
Typed transaction view model
      ↓
Status + relationship selectors
      ├── Sankey / timeline projections
      ├── Provenance graph projection
      ├── Event table projection
      └── JSON / diff projection
      ↓
Linked detail drawer + verification panel
```

The first visual design direction is **clinical operations console**: a quiet neutral canvas, dense but readable data tables, one high-salience verification accent, and status colors paired with text/patterns. Motion is reserved for live progress and playback; reduced-motion mode is required. Avoid 3D effects, decorative dashboards, and charts that cannot be traced back to an event or metric definition.

## 9. Non-functional requirements

### Security and privacy

- No raw PHI, secrets, access tokens, or full prompt/context payloads are written to the append-only audit store by default.
- Clinical content references are opaque, access-controlled, and resolvable only by an authorized service.
- Hashes, identifiers, timestamps, and metadata are treated as potentially sensitive because they may support linkage or re-identification.
- Every service-to-service call is authenticated in the prototype environment; production design must support organization-managed identity and key rotation.
- Audit UI access is role-based and itself produces an audit event.
- Retention and deletion policies are explicit. Deleting clinical content must not be described as deleting the historical proof; the resulting state must be represented as unavailable/redacted while preserving integrity metadata.

### Reliability and integrity

- Events are append-only from the application’s perspective; corrections are represented by linked compensating events, never silent mutation.
- The verifier must detect event mutation, event omission, event reordering, broken chain links, invalid Merkle proofs, and invalid signatures.
- Partial or failed transactions remain visible with a terminal failure state.
- The system must fail closed when required provenance fields cannot be captured.

### Performance targets for the prototype

- Capture overhead: report incremental latency and storage versus an identical unrecorded clinical workflow; do not claim a 15% target unless that measured ratio is below 15%.
- Verification: verify a single transaction in under 1 second on the reference development machine for the target event volume.
- UI load: render a transaction with up to 100 events in under 2 seconds locally after data retrieval.
- Availability: not a production SLA for the prototype; test restart/recovery behavior and document limitations.
- Interactive chart selections and table filters should respond locally in under 100 ms for a loaded transaction view.
- The event table should remain usable for at least 1,000 loaded events through virtualization; larger result sets must use server-side pagination or filtering.
- The Sankey, graph, timeline, and table must degrade to an accessible tabular representation when graphics are unavailable.

### Interoperability and maintainability

- Use versioned JSON schemas and canonical serialization rules.
- Keep FHIR mappings separate from internal event schemas.
- Isolate LLM and retrieval providers behind adapters.
- Every event includes schema version and producer version.
- All prototype runs are reproducible from a checked-in fixture, configuration manifest, and seed where applicable.
- Statuses are represented as machine-readable enum values and human-readable labels; color is never the only status signal.
- The UI supports keyboard navigation, readable table headings, visible focus, and text alternatives for status icons.

## 10. Proposed architecture

```text
┌─────────────────────┐
│ Synthetic FHIR      │
│ server / fixtures    │
└──────────┬──────────┘
           │ authorized read
           ▼
┌─────────────────────┐       ┌──────────────────────┐
│ Context builder      │──────▶│ Clinical content      │
│ + input manifest     │ ref   │ store / fixture repo  │
└──────────┬──────────┘       └──────────────────────┘
           │ context + digest
           ▼
┌──────────────────────────────────────────────────────┐
│ Transaction orchestrator                              │
│ model adapter · prompt manifest · RAG · tool adapter   │
└──────────┬───────────────────────────────────────────┘
           │ structured AI output
           ▼
┌─────────────────────┐
│ Output schema +      │
│ guardrail engine     │
└──────────┬──────────┘
           │ review packet
           ▼
┌─────────────────────┐       ┌────────────────────────┐
│ Clinician review UI  │──────▶│ Human action / final    │
└─────────────────────┘       │ output                  │
                              └──────────┬─────────────┘
                                         │ events
                                         ▼
                              ┌────────────────────────┐
                              │ Audit plane              │
                              │ event store + verifier   │
                              │ chain + Merkle + signing │
                              └──────────┬─────────────┘
                                         │
                      ┌──────────────────┴─────────────────┐
                      ▼                                    ▼
             ┌──────────────────┐                 ┌─────────────────┐
             │ Audit/replay UI   │                 │ FHIR export     │
             │ + verification    │                 │ Provenance/     │
             │ report            │                 │ AuditEvent      │
             └──────────────────┘                 └─────────────────┘
```

### Recommended prototype implementation shape

Use a small service or modular monolith with an append-oriented relational store, a protected content store, and a separate verification library. The architecture should be easy to run locally and easy to replace piece by piece later.

- FHIR boundary: one FHIR server or fixture loader.
- Orchestration: one transaction API that emits typed events.
- LLM boundary: provider adapter plus deterministic stub.
- Retrieval: local versioned corpus with stable chunk IDs and digests.
- Audit store: relational tables for events/manifests and object storage or local files for larger protected payloads.
- Integrity: canonical JSON → SHA-256 event hashes → transaction chain → Merkle batch → Ed25519 signature.
- UI: React/TypeScript audit console with Apache ECharts, TanStack Table, JSON inspection, evidence links, review actions, and verification status. React Flow, playback, and SSE remain deferred P1.

The prototype should not introduce a blockchain. A signed, append-oriented event store with independently verifiable proofs is sufficient to test the research hypothesis.

### Relationship to the existing Curie projects

Curie Audit Plane should be a standalone shared provenance component with adapters into the existing Curie project family. It should not duplicate the clinical pipelines or replace their domain responsibilities.

| Existing project | Relationship to Curie Audit Plane | Prototype decision |
|---|---|---|
| `curie-fhir` | Primary first integration. It already has FHIR ingestion, context construction, RAG, model execution, validation/correction traces, provenance envelopes, human review, a run-history store, and a J-BHI paper package. | Build the first end-to-end adapter around its FHIR-to-LLM transaction. Reuse its synthetic fixtures and review concepts; emit the new typed audit events at the workflow boundaries. |
| `curie-prediction-pipeline` | Next integration target. It produces event-time clinical signals, governed alerts, evidence IDs, versioned rule bundles, and post-alert narratives. | Keep alert firing deterministic and outside the LLM path. Later capture alert, rule, evidence, and narrative provenance through an adapter. It is not required for the first prototype. |
| `curie-gateway` | Future security and access-event source. It records tenant registration, token, certificate, and proxied FHIR request outcomes. | Treat gateway events as a later connector for access provenance and tenant-level audit. Do not make UDAP/TEFCA onboarding an MVP dependency. |
| `personal-ai` | Frontend and workflow reference. Its React/Vite, TanStack Query, SSE trace, responsive UI, and Playwright patterns can inform the audit console. | Reuse patterns selectively; the audit console remains a healthcare-specific product surface with stronger status, access, and verification requirements. |
| `pareto-context-graph` | Developer-side context-ranking and observability tooling. | Optional engineering aid only; not part of the clinical runtime or audit evidence model. |

The other inspected projects—disaster analytics, RSVP/portfolio applications, CRM exercises, stock forecasting, and MLX/TurboQuant experiments—are not direct runtime dependencies for this healthcare prototype. They may provide isolated engineering patterns, but adding them to the product boundary would dilute the research question.

**Integration order:** `curie-fhir` → `curie-prediction-pipeline` → `curie-gateway`. The first release must prove that Curie Audit Plane can observe one complete clinical AI transaction before it expands to cross-product or organization-wide audit coverage.

## 11. Data model

The internal schema is versioned. The examples below describe the minimum logical model, not a final database schema.

### Status taxonomy

Statuses are part of the audit contract and must be rendered consistently in the API, JSON, tables, and UI.

| Status family | Values | Meaning |
|---|---|---|
| Transaction | `STARTED`, `RUNNING`, `WAITING_FOR_REVIEW`, `COMPLETED`, `FAILED`, `BLOCKED`, `INCOMPLETE`, `TAMPERED` | Overall lifecycle and trust state of a transaction |
| Event | `RECORDED`, `VERIFIED`, `WARNING`, `FAILED`, `MISSING`, `TAMPERED` | Capture and integrity state of an individual event |
| Guardrail | `PASS`, `WARN`, `BLOCK`, `ERROR` | Result of a safety or policy check |
| Verification | `NOT_RUN`, `VERIFIED`, `INCOMPLETE`, `FAILED`, `TAMPERED` | Result of checking the requested proof scope |
| Human action | `PENDING`, `ACCEPT`, `MODIFY`, `REJECT` | Reviewer disposition of the AI output |

The API should expose both the enum value and a display label. A transaction may be `COMPLETED` from a workflow perspective but still show a failed verification state; the UI must display those dimensions separately rather than collapse them into one green/red indicator.

### Core entities

| Entity | Purpose | Required fields |
|---|---|---|
| `Transaction` | Bounded FHIR-to-LLM workflow | `transaction_id`, status, purpose, subject reference, start/end time, schema version |
| `AuditEvent` | One observable event in the workflow | event ID, transaction ID, sequence, type, actor/service, time, payload reference, payload digest, previous hash, event hash |
| `InputManifest` | Exact source inventory | resource reference, source system, version/time, selection reason, content reference, digest |
| `Transformation` | Reproducible data change | operation ID/name, code version, parameters digest, input refs, output ref, output digest |
| `ModelManifest` | Execution configuration | model/provider ID, endpoint, model version, prompt version, decoding params, tool policy, runtime, seed if supported |
| `EvidenceItem` | Patient or external support | evidence ID, source type, source ref, corpus/document/chunk version, rank/score, digest, output links |
| `ToolCall` | External or internal tool execution | tool ID/version, argument reference/digest, result reference/digest, status, sequence |
| `StructuredOutput` | AI-produced decision artifact | protected content reference, schema version, evidence refs, uncertainty metadata, missing-data metadata, digest |
| `GuardrailResult` | Safety/policy evaluation | rule ID/version, scope, result, severity, message, override requirement, digest |
| `HumanAction` | Reviewer disposition | action, actor, role, time, comment, source output ID, protected final-output reference/digest |
| `IntegrityBatch` | Batch proof | batch ID, ordered transaction roots, Merkle root, signature, key ID, signing time |

### Event sequence for the first transaction

1. `transaction.started`
2. `input.manifest.created`
3. `transformation.applied` (one or more)
4. `context.manifest.created`
5. `retrieval.completed` (if enabled)
6. `tool.called` / `tool.completed` (if enabled)
7. `model.requested`
8. `model.responded`
9. `structured_output.validated`
10. `guardrail.completed` (one or more)
11. `human.action_recorded`
12. `transaction.completed` or `transaction.failed`
13. `integrity.proof_committed`

The sequence must tolerate optional events while preserving required-event rules. A failed transaction may end before human review but must state why and which required artifacts are absent.

### FHIR mappings

The prototype will create documented mappings rather than pretend that one FHIR resource can represent the entire audit plane.

- **FHIR `Provenance`:** represent the generated structured output or final clinical artifact, its agents (AI service and reviewer), activities, recorded time, target references, and relevant entities such as source FHIR resources and the prompt/model manifest.
- **FHIR `AuditEvent`:** represent access to source resources, AI execution, retrieval/tool activity, guardrail evaluation, human review, export, and verification. Use event subtype or extension fields for transaction ID, event hash, and proof references where the chosen profile permits.
- **Internal audit events:** remain the lossless source for detailed cryptographic and operational fields. FHIR resources are interoperable projections, not a replacement for the internal event model.

## 12. Threat model

### Assets

- Patient clinical content and identifiers.
- Input, transformation, evidence, model, and prompt manifests.
- Structured AI output and human disposition.
- Audit event ordering and integrity proofs.
- Signing keys and verification keys.
- Access history and exported audit packages.

### Threats and controls

| Threat | Example | Prototype control |
|---|---|---|
| PHI leakage | Raw note or prompt is copied into immutable logs | Content/reference separation, payload allowlist, secret/PHI checks, protected store |
| Event mutation | Operator changes model version or guardrail result | Canonical hashes, chain verification, signed Merkle root |
| Event deletion or reordering | A failed guardrail event is removed | Sequence numbers, previous-hash links, required-event completeness checks |
| Selective omission | Tool call or retrieved evidence is not recorded | Instrument adapters at the boundary; completeness metric; fail-closed status |
| Replay substitution | Investigator replays with a newer model or corpus | Versioned manifests and content digests; explicit replay comparison |
| Key compromise | Attacker signs false audit batches | Key ID, protected key storage boundary, rotation/revocation design, signature status |
| Unauthorized investigation | Reviewer sees unrelated patient data | Role-based access, opaque references, scoped transaction access, audit UI logging |
| Linkage attack | Hashes or timestamps help identify a patient | Treat metadata as sensitive; minimize fields; access control; retention policy |
| Malicious or faulty model output | Confident but unsupported summary | Structured evidence references, uncertainty field, guardrails, human disposition |
| Guardrail bypass | Human override is hidden or unrecorded | Explicit override event, actor/comment, policy version, terminal status |
| Provider-side nondeterminism | Same request produces a different output | Capture provider/configuration, use deterministic stub, classify replay as exact/equivalent/divergent |
| Audit-plane outage | AI output exists but provenance is missing | Transaction blocks completion or is visibly marked non-auditable; retry/recovery test |

### Trust boundaries

1. FHIR source to context builder.
2. Context builder to model/RAG/tool providers.
3. AI output to guardrail and reviewer UI.
4. Application services to audit store.
5. Audit store to verifier/exporter.
6. Signing service/key boundary.

Each boundary must have an event-producing adapter or explicit limitation in the completeness report.

## 13. Milestones and deliverables

### Phase 0 — Research framing and fixtures (Week 1)

- Freeze use case, event taxonomy, required-event rules, and metric definitions.
- Create synthetic FHIR fixtures and a small versioned evidence corpus.
- Write schema and threat-model tests before wiring a live model.

**Exit:** A fixture transaction can be described end to end on paper and in JSON examples.

### Phase 1 — Capture and integrity core (Weeks 2–3)

- Implement transaction/event model, canonicalization, hashes, chain verification, and test fixtures.
- Implement input manifest and transformation events.
- Implement protected content references and redaction checks.

**Exit:** Mutation, omission, reorder, and invalid-signature tests fail verification as expected.

### Phase 2 — AI execution and evidence (Weeks 4–5)

- Add LLM adapter and deterministic stub.
- Add prompt/model manifests, structured output validation, retrieval evidence, and tool events.
- Add guardrail engine and failed-run behavior.

**Exit:** A complete synthetic transaction produces an auditable package with no raw PHI in the audit store.

### Phase 3 — Human review and UI (Weeks 6–7)

- Implement timeline, event details, evidence links, guardrail display, and human actions.
- Add FHIR `Provenance`/`AuditEvent` projection and verification report.

**Exit:** A new reviewer can inspect and disposition a transaction; an investigator can verify it independently.

### Phase 4 — Evaluation and IEEE paper package (Weeks 8–9)

- Run the benchmark across clean, incomplete, and tampered transaction sets.
- Measure completeness, detection, replay, overhead, and usability.
- Package architecture, schemas, threat model, limitations, reproducibility materials, and results for an IEEE paper submission.

**Exit:** Results are reproducible from a documented command/configuration and the limitations are explicit.

### Phase 5 — Product discovery (after prototype)

- Interview provider, health IT, AI vendor, security, and compliance stakeholders.
- Validate deployment models, retention/key-management requirements, and integration priorities.
- Define a pilot with synthetic or approved limited data under institutional review.

**Exit:** A pilot design partner, deployment boundary, success criteria, and ownership model are identified.

## 14. Acceptance criteria for the first prototype

The prototype is complete when all of the following are true:

1. A synthetic FHIR bundle can flow through context building, optional retrieval, LLM/stub execution, structured output validation, guardrails, human review, and completion.
2. The resulting transaction contains all required P0 event types or an explicit failure explaining which event is missing.
3. The input manifest identifies every FHIR resource and derived context item used by the model.
4. Every transformation is recorded with enough information to reproduce its output digest.
5. The model/prompt manifest distinguishes at least two model or prompt configurations.
6. Every retrieved evidence item shown to a reviewer is present in the audit record with a stable ID and digest.
7. Tool calls, when enabled, are visible and linked to the structured output.
8. Structured rationale includes evidence references and uncertainty, and no hidden chain-of-thought is captured.
9. Guardrail pass, warning, block, and explicit human override paths are tested.
10. ACCEPT, MODIFY, and REJECT are each demonstrated and linked to the final disposition.
11. Independent verification detects every mutation, deletion, reorder, broken link, invalid Merkle proof, and invalid signature in the tamper test suite.
12. At least 95% of required provenance fields are reconstructable in the benchmark; missing fields are counted rather than silently ignored.
13. FHIR `Provenance` and `AuditEvent` projections are generated and validated against documented mapping rules.
14. A reviewer can inspect a transaction and understand its lifecycle without reading source code.
15. The prototype documentation clearly states that it is not a clinical deployment or regulatory certification.
16. The transaction overview displays lifecycle status, verification status, event counts, and missing/failed-event counts.
17. The event timeline and event table expose every P0 event and allow sorting/filtering by sequence, time, type, actor, and status.
18. Every event and manifest has formatted JSON and raw JSON views with schema version, digest, and copy/download controls.
19. Input, transformation, model/prompt, evidence, tool, guardrail, output, and human-action data are available in readable tables.
20. Status values match the defined taxonomy and remain understandable when color is removed.
21. The UI links related inputs, transformations, evidence, tools, outputs, guardrails, human actions, and integrity proofs.
22. The verification panel reports chain, Merkle, signature, key ID, scope, and verification time.
23. The reviewer can distinguish AI-generated output, human-modified output, replay output, and their digests.
24. UI access and export actions are themselves captured as audit events.
25. The interactive Sankey renders the P0 transaction stages from FHIR inputs through integrity proof and links each node/edge to the underlying records.
26. Selecting a Sankey node or edge filters the event table and JSON detail view to the same provenance slice, with a clear reset action.
27. Sankey and timeline views declare their metric semantics, show text-based statuses, and provide an accessible tabular fallback.

## 15. Evaluation plan

### Research questions

1. Can a provenance layer reconstruct the observable basis of a clinical AI output without storing hidden chain-of-thought or raw PHI in an immutable store?
2. How reliably does the integrity scheme detect mutation, omission, reordering, and proof substitution?
3. What latency and storage overhead does complete capture introduce?
4. Can the transaction UI expose evidence, uncertainty, guardrail failures, and human disposition as recorded artifacts? Answered as a system demonstration with `SCRIPTED_PROXY` reconstruction, not a human-subject usability study.
5. How much replay fidelity is possible for a deterministic stub versus a hosted nondeterministic model?

### Benchmark design

Create a controlled benchmark of synthetic FHIR transactions with:

- Clean complete runs.
- Missing input, transformation, evidence, tool, guardrail, or human-action events.
- Mutated fields such as model version, output, timestamp, or reviewer action.
- Deleted and reordered events.
- Wrong content references and wrong corpus versions.
- Invalid or substituted signatures.
- Deterministic stub runs and selected hosted-model runs to characterize replay limits.

### Metrics

| Metric | Definition | Target for prototype |
|---|---|---|
| Audit Reconstruction Completeness (ARC) | Required provenance fields successfully reconstructed from persisted records and independently verified ÷ total required fields (`independently_verified_arc`); report `field_presence_arc` separately | ≥95% independently verified on clean benchmark; no silent missing fields |
| Required-event completeness | Required event types present with valid links ÷ required event types | 100% for successful transactions |
| Tamper detection rate | Tampered benchmark cases correctly flagged ÷ all tampered cases | 100% for defined mutation suite |
| False tamper rate | Untampered cases incorrectly flagged ÷ all clean cases | 0% on fixture benchmark |
| Replay fidelity | Runs classified exact/equivalent/divergent using predefined comparison rules | Report by provider/configuration; no universal target for nondeterministic models |
| Evidence attribution coverage | Output claims with valid evidence references ÷ claims requiring evidence | ≥90% in structured-output benchmark |
| Human-action capture completeness | Completed runs with actor, action, time, and final-output digest ÷ runs reaching review | 100% |
| Capture overhead | Added latency and storage relative to an identical unrecorded clinical workflow | Report measured ratio; do not claim <15% unless that baseline is met |
| Verification latency | Time to verify one transaction and one batch proof | <1 second locally for target fixture size |
| Reviewer task success | Correctly identify source, model, evidence, guardrail, and human action in a timed task | `SCRIPTED_PROXY` only; no human-subject usability claim in this paper |

### Experimental discipline

- Version fixtures, schemas, model manifests, corpus, and benchmark mutations.
- Separate capture completeness from clinical correctness; the prototype does not establish clinical efficacy.
- Report provider/model nondeterminism rather than hiding it behind a replay claim.
- Include negative results and known blind spots in the paper.

## 16. Research paper shape

The prototype can support a paper organized around:

1. Motivation: the gap between model logs and verifiable clinical AI provenance.
2. Design: data/proof separation, event model, FHIR mappings, and cryptographic integrity.
3. Prototype: one FHIR-to-LLM workflow with structured rationale and human review.
4. Threat model: mutation, omission, leakage, replay substitution, and key compromise.
5. Evaluation: independently verified ARC, field-presence ARC, tamper detection with labeled mutations, replay fidelity, overhead versus application logging, and `SCRIPTED_PROXY` reviewer-field reconstruction.
6. Limitations: synthetic data, narrow workflow, provider nondeterminism, incomplete clinical semantics, operational key management, and no clinical efficacy claim.
7. Future work: multi-agent workflows, longitudinal monitoring, deployment pilots, policy packs, and independent third-party verification.

### IEEE publication track

The prototype should be developed with an IEEE submission in mind. The primary target is **IEEE Journal of Biomedical and Health Informatics (J-BHI)**; venue selection should still be reconfirmed against the current author instructions after the evaluation results are known. Candidate fallback paths include:

- **IEEE Access:** a broad applied-research route for a complete technical prototype, quantitative evaluation, and reproducible artifact package.
- **IEEE EMBC/EMBS conference route:** a shorter biomedical-engineering paper emphasizing healthcare relevance, system design, and initial experimental results.

J-BHI is a good fit only if the manuscript frames CAP as a biomedical and health-informatics method for secure, interoperable, and reviewable clinical information systems—not merely as a generic LLM logging tool. The J-BHI scope describes work at the intersection of information and communication technologies with health, healthcare, life sciences, and biomedicine, including electronic medical records, clinical information systems, decision support, interoperability, and secure patient data. ([J-BHI scope](https://www.embs.org/jbhi/articles/jbhi/))

The team must verify J-BHI’s current scope, article type, template, page limits, review model, fees, originality rules, and supplementary-material requirements before formatting the manuscript. IEEE Access remains a practical fallback because its guidance explicitly expects original work, technically sound experiments, supported conclusions, and permits supplemental code/data; its submission guidance also addresses disclosure of AI-generated text. ([IEEE Access author guidance](https://ieeeaccess.ieee.org/authors/preparing-your-article/))

### Expected paper contribution

The paper should make a precise, defensible claim:

> A FHIR-to-LLM provenance plane can make the observable basis of a clinical AI transaction reconstructable and tamper-evident, with measurable completeness and integrity detection, without storing hidden chain-of-thought or raw PHI in the immutable audit store.

The contribution should be supported by:

1. A versioned event and manifest model for FHIR inputs, transformations, model/prompt configuration, evidence, tools, guardrails, and human disposition.
2. A data/proof separation architecture with hash chains, Merkle batching, signatures, and FHIR projections.
3. An interactive audit-console design that links Sankey flow, timeline, tables, JSON, evidence, and verification records.
4. A benchmark containing clean, incomplete, mutated, deleted, reordered, and proof-substitution cases.
5. Quantitative results for ARC, tamper detection, replay fidelity, evidence coverage, human-action capture, latency, and storage overhead.

### J-BHI-specific framing requirements

- Tie the problem to EHR/FHIR-based clinical information systems and the human review workflow.
- Demonstrate why provenance completeness and tamper detection matter for safe biomedical or health-informatics use, not only for software observability.
- Include at least one healthcare-specific baseline or comparison, such as ordinary clinical application logs or FHIR-only provenance without the complete audit plane.
- Report the clinical-data boundary, synthetic-data generation, access assumptions, and limitations clearly.
- Separate claims about auditability, security, interoperability, and usability from claims about clinical accuracy or patient outcomes.
- Include a health-informatics discussion of how the approach could integrate with existing EHR/FHIR workflows.

### IEEE-ready artifact package

Before submission, the project should produce:

- IEEE-formatted manuscript source and PDF.
- Reproducible synthetic FHIR fixtures and versioned evidence corpus.
- Event schemas, canonicalization rules, verifier, benchmark generator, and evaluation scripts.
- Configuration manifests, dependency versions, model/provider details, and seeds where applicable.
- Baseline implementations: ordinary application logging, hash-only logging, and the complete provenance plane.
- Screenshots or a short demonstration of the Sankey, event table, JSON inspector, verification panel, and replay comparison.
- Threat model, limitations, data-handling statement, and an explicit statement that the prototype does not establish clinical efficacy or regulatory clearance.
- Ethics/IRB statement if human reviewers participate in the usability evaluation; no real patient data should be required for the first paper.
- Author-contribution record and AI-assistance disclosure appropriate to the selected IEEE venue.

### Publication gates

- **Gate A — contribution freeze:** the event model, research questions, baselines, and primary metrics are fixed before final experiments.
- **Gate B — reproducibility freeze:** a clean environment can regenerate the headline tables and figures from synthetic fixtures.
- **Gate C — integrity freeze:** the verifier and tamper benchmark are independently exercised by someone who did not implement them.
- **Gate D — venue check:** the current J-BHI author instructions, scope, originality policy, template, and artifact rules are reviewed immediately before submission; IEEE Access/EMBC are retained as fallback routes.

The paper and any future commercial product should remain separate work products: the paper emphasizes novelty, evidence, and limitations; the product plan emphasizes deployment, security operations, integrations, support, and customer value.

## 17. Commercial product direction

### Likely product

A clinical AI governance and provenance service that integrates with an organization’s FHIR/EHR environment and AI gateway. It would provide:

- Transaction-level audit and replay packages.
- Policy and guardrail observability.
- Model/prompt/evidence lineage.
- Human review accountability.
- Independent verification for investigations and vendor oversight.
- Organization-controlled storage, retention, encryption, and signing keys.
- FHIR-native exports and APIs for governance workflows.

### Product phases

- **Research prototype:** synthetic data, one workflow, local deployment, benchmark and paper.
- **Design-partner pilot:** one approved clinical workflow, controlled data boundary, SSO/RBAC, operational monitoring, key management, and formal privacy/security review.
- **Commercial v1:** multi-tenant or customer-hosted deployment, connectors, policy packs, retention controls, SIEM/export integrations, supportability, and documented assurance processes.

### Product risks to validate before selling

- Whether customers value reconstruction and tamper evidence enough to fund integration.
- Whether audit metadata itself creates unacceptable privacy or operational burden.
- Whether FHIR mappings satisfy real governance workflows or require additional formats.
- Whether model vendors expose sufficient execution metadata.
- Who owns the signing keys, source content, retention policy, and incident response.
- Whether the product is positioned as governance infrastructure, clinical software, or both.

## 18. Open questions

1. Which exact clinical summary variant should be fixed for the benchmark: encounter summary, longitudinal summary, or discharge-style summary?
2. Should the first RAG corpus be patient-context retrieval only, external clinical guidance only, or both?
3. Which FHIR version and profile should define the initial mapping target?
4. What is the minimum structured rationale schema clinicians find useful without implying hidden reasoning access?
5. Which guardrails are in scope for the first benchmark: schema validation, unsupported-claim detection, PHI leakage, contraindication rules, or all four?
6. How should modified human output be represented when it contains new content not generated by the AI?
7. What replay equivalence rules are acceptable for a nondeterministic hosted model?
8. Is the immutable boundary a database table, append-only object store, or a separately operated verification service in the first deployment?
9. Which signing-key lifecycle should be simulated in the prototype, and which requires a security-reviewed service in a pilot?
10. What level of de-identification is required for research exports and paper artifacts?
11. Which reviewer tasks and participant population are feasible for a usability study?
12. What evidence would convince a provider or AI vendor to run a design-partner pilot?

## 19. Decisions deferred until after the prototype

- Public versus private ledger architecture.
- Multi-organization trust and cross-institution verification.
- Full longitudinal patient timeline and continuous monitoring.
- Multi-agent orchestration and agent-to-agent provenance.
- Production-grade key management and hardware-backed signing.
- Automated clinical correctness scoring.
- Regulatory classification and clinical deployment pathway.

## 20. Definition of done for the PRD

This PRD is ready to guide implementation when the team agrees on the single workflow, the required event sequence, the ARC/tamper benchmark, the no-PHI immutable-store boundary, and the prototype exit criteria. The open questions above should be resolved only when they materially affect implementation or evaluation.
