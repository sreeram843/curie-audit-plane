# Curie Audit Plane

Clinical AI Flight Recorder for verifiable, privacy-aware provenance around FHIR-to-LLM workflows.

## What this project is

Curie Audit Plane records the observable provenance of a bounded clinical AI transaction:

```text
FHIR inputs -> transformations -> context -> RAG/tools -> model
    -> structured output -> guardrails -> human action -> integrity proof
```

The first release is a research prototype using synthetic FHIR data. It is designed to answer:

> Can an investigator reconstruct what a clinical AI system saw, how it was configured, what evidence and safeguards were involved, and what a human decided—while keeping raw clinical payloads outside the immutable audit store?

This repository does not claim clinical validation, regulatory clearance, or access to hidden model chain-of-thought.

## Prototype boundary

- One end-to-end synthetic FHIR-to-LLM transaction.
- One structured clinical-summary workflow.
- Input manifest and transformation records.
- Model, prompt, retrieval, and tool manifests.
- Structured rationale with evidence references and uncertainty.
- Guardrail results and human ACCEPT/MODIFY/REJECT actions.
- FHIR `Provenance` and `AuditEvent` projections.
- SHA-256 event hashes, hash chaining, Merkle roots, and Ed25519 signatures.
- Interactive audit UI with timeline, tables, JSON inspection, verification, replay comparison, and Sankey of recorded artifact flow (React Flow provenance graph is deferred).

## Documentation

- [Agent Guide](AGENTS.md)
- [Skills and Workflows](docs/skills-and-workflows.md)
- [Product Requirements Document](docs/PRD.md)
- [Architecture](docs/architecture.md)
- [Research and J-BHI Plan](docs/research-plan.md)
- [Domain Glossary](CONTEXT.md)
- [Prototype Implementation Plan](docs/superpowers/plans/2026-08-27-curie-audit-plane-prototype.md)
- [FHIR Mapping](docs/fhir-mapping.md)
- [TDD Evidence](docs/testing/prototype.tdd.md)
- [Stack ADR](docs/adr/0001-prototype-stack-and-event-contract.md)

## Relationship to the Curie project family

The first adapter observes `curie-fhir` concepts (FHIR R4 resources, synthetic fixtures, provenance envelopes, human review) without importing or replacing that pipeline. Later integrations may observe `curie-prediction-pipeline` and `curie-gateway`.

## Current status

First vertical slice is implemented locally:

- Synthetic FHIR R4 encounter bundle → context → LLM (deterministic stub by default, or local LM Studio) → guardrails → ACCEPT/MODIFY/REJECT → hash chain / Merkle / Ed25519.
- FastAPI plus React audit console (timeline, table, JSON, verification, replay, Sankey with artifact-count metric). The React Flow provenance graph is not available in this prototype.
- Fail-closed bearer-token prototype auth with reviewer / investigator / admin roles.
- Access and export events are recorded in a separate hash-chained access-audit stream so the clinical proof stays sealed.
- ARC and tamper-detection benchmark against fixtures.

Deferred: hosted cloud LLM, `curie-prediction-pipeline` / `curie-gateway` adapters, React Flow provenance graph, playback scrubber, global search, SSE/live updates, production HSM/key rotation, multi-tenant access control, and any clinical or regulatory claim.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
curie-audit-plane setup   # writes generated CAP_ADMIN_TOKEN and VITE_CAP_AUTH_TOKEN; do not commit .env
curie-audit-plane run --action ACCEPT
curie-audit-plane evaluate --output-dir evaluation-results --encounters 50 --repetitions 1
curie-audit-plane serve --port 8090   # API + built console at http://127.0.0.1:8090
# or, during UI development:
curie-audit-plane serve              # API on http://127.0.0.1:8080
cd console && npm install && npm run dev   # UI on http://127.0.0.1:5173
```

Use synthetic fixtures only. Signing keys are written under `data/keys/` and are gitignored.

The evaluation command uses the completer from `CAP_LLM_PROVIDER` (`stub` or local
`openai_compatible`). Default paper command:

```bash
curie-audit-plane evaluate --output-dir evaluation-results --encounters 50 --repetitions 1
```

Keep stub and live-model reports in separate output directories. The run accepts
`--encounters 1..1000` and `--repetitions 1..1000`. It writes `evaluation-report.json`,
`evaluation-metrics.csv`, and the vector figure `evaluation-cohort-metrics.svg`. The report
contains metric values, numerators, denominators, benchmark cases, baseline observations, capture
overhead, replay classification, and explicit status labels for scripted proxies. It contains no
raw FHIR payloads, prompts, tokens, or signing keys. Results are prototype measurements, not clinical
efficacy or regulatory evidence.

To send the bounded context to a local LM Studio model instead of the stub, set in `.env`:

```bash
CAP_LLM_PROVIDER=openai_compatible
CAP_LLM_BASE_URL=http://127.0.0.1:1234/v1
CAP_LLM_MODEL=medgemma-4b-it-mlx
```

Then restart `curie-audit-plane serve`. Tests keep using the stub unless a completer is injected. Hosted-model replay is never `EXACT_MATCH`; matching output is `EQUIVALENT`, and missing recorded configuration is `NOT_REPLAYABLE`.

API requests require a bearer token from `.env` (`CAP_ADMIN_TOKEN`, or a role-specific `CAP_REVIEWER_TOKEN` / `CAP_INVESTIGATOR_TOKEN`). Copy `.env.example` to `.env` and run `curie-audit-plane setup` so tokens are generated locally; do not put tokens in source, `.env.example`, or localStorage. The console sends `VITE_CAP_AUTH_TOKEN` from the environment. The API will not start in an authenticated mode until at least one role token is set. Restart the API and Vite console after setup.
