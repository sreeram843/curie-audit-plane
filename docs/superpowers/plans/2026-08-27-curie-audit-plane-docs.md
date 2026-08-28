# Curie Audit Plane Documentation Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a documentation-first repository foundation for the Curie Audit Plane research prototype.

**Architecture:** Keep the audit plane as a standalone provenance boundary with a first adapter around one synthetic FHIR-to-LLM transaction. Separate protected clinical payloads from immutable audit metadata and integrity proofs; defer runtime implementation until the event contract and evaluation plan are stable.

**Tech Stack:** Markdown documentation; FHIR R4 concepts; canonical JSON; SHA-256; hash chains; Merkle roots; Ed25519 signatures; React/TypeScript audit-console direction; Python/ FastAPI-compatible integration direction.

**Spec:** `docs/PRD.md`

## Global Constraints

- Use synthetic FHIR data only for the first prototype.
- Do not store raw PHI or hidden chain-of-thought in the immutable audit store.
- Keep the first transaction bounded from FHIR input acquisition through human ACCEPT/MODIFY/REJECT disposition.
- Treat the UI, machine-readable JSON, tables, statuses, and interactive provenance visualizations as first-class requirements.
- Measure Audit Reconstruction Completeness and tamper detection before making commercial or clinical claims.

---

### Task 1: Repository documentation foundation

**Files:**
- Create: `.gitignore`
- Create: `CONTEXT.md`
- Modify: `README.md`

- [x] Add repository hygiene rules for local artifacts and generated dependencies.
- [x] Add the domain glossary for Curie Audit Plane terminology.
- [x] Update the README with project purpose, prototype boundary, documentation links, and explicit non-clinical status.
- [x] Verify all README links point to files created in this documentation pass.

### Task 2: Product and architecture documentation

**Files:**
- Create: `docs/PRD.md`
- Create: `docs/architecture.md`

- [x] Add the complete prototype PRD, including scope, non-goals, users, requirements, data model, threat model, milestones, acceptance criteria, evaluation, J-BHI publication path, and commercial direction.
- [x] Add a concise architecture guide showing the FHIR-to-context-to-LLM flow, protected content boundary, audit events, integrity verifier, FHIR projections, and UI.
- [x] Document the integration order: `curie-fhir`, then `curie-prediction-pipeline`, then `curie-gateway`.
- [x] Keep neighboring Curie projects’ domain responsibilities explicit; the audit plane observes and verifies workflows rather than replacing them.

### Task 3: Research and publication documentation

**Files:**
- Create: `docs/research-plan.md`

- [x] Define research questions, benchmark cases, baselines, metrics, reproducibility artifacts, and reviewer usability tasks.
- [x] State the evidence gates required before a J-BHI submission.
- [x] Separate auditability and integrity claims from clinical efficacy and regulatory claims.

### Task 4: Documentation verification

**Files:**
- Read: `README.md`, `CONTEXT.md`, and all files under `docs/`

- [x] Check that required sections are present and terminology is consistent.
- [x] Check that no document promises hidden chain-of-thought access, clinical validation, or regulatory clearance.
- [x] Check Git status and preserve any pre-existing untracked files.
