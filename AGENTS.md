# Curie Audit Plane agent guide

## Start here

Before changing behavior, read these documents in order:

1. `CONTEXT.md` — canonical domain vocabulary.
2. `docs/PRD.md` — scope, requirements, acceptance criteria, and research claims.
3. `docs/architecture.md` — system boundaries and data/proof separation.
4. `docs/research-plan.md` — benchmark, baselines, metrics, and publication gates when research work is involved.

For UI work, also read the audit-console requirements in `docs/PRD.md` and follow the browser-verification rule in `.cursor/rules/ironbee-devtools-use.mdc`.

## Product boundary

Keep the first implementation narrow: one synthetic FHIR-to-LLM transaction from input acquisition through guardrails and human ACCEPT/MODIFY/REJECT disposition. The first adapter targets `curie-fhir`; `curie-prediction-pipeline` and `curie-gateway` are later integrations.

The audit plane observes and verifies neighboring systems. It does not replace the FHIR pipeline, deterministic alert-governance path, FHIR access gateway, LLM provider, or clinical reviewer.

## Non-negotiable safety rules

- Keep raw clinical payloads in an authorized protected-content store or fixture repository.
- Keep immutable audit records limited to metadata, opaque references, schemas, and digests needed for verification.
- Represent model explanation as structured rationale with evidence, uncertainty, assumptions, and missing data.
- Do not create or persist hidden chain-of-thought fields.
- Use synthetic FHIR data until a separate approved data-handling boundary exists.
- Never hardcode API keys, tokens, passwords, signing keys, or patient data.
- Validate inputs at every API, file, tool, and model boundary.
- Treat audit metadata, hashes, timestamps, and subject references as sensitive.

## Required engineering workflow

1. Derive observable acceptance criteria and explicit non-goals before implementation.
2. Reuse an existing Curie seam before adding a provider, service, database, or abstraction.
3. For code changes, write tests first, prove a meaningful RED state, implement the smallest GREEN change, then run coverage and integration checks.
4. Run a security review for authentication, authorization, user input, secrets, APIs, storage, FHIR content, tool calls, or external providers.
5. For UI changes, use intentional audit-console information design: timeline, tables, formatted/raw JSON, status text, verification scope, linked records, and accessible fallbacks. Visualizations must expose recorded relationships, not imply causality.
6. For research claims, use primary sources, version fixtures/configuration, record negative results, and keep auditability separate from clinical efficacy.
7. Before handoff, verify the focused acceptance criteria, inspect the diff, check for secrets or PHI, and report unavailable or unresolved checks explicitly.

## Contract vocabulary

Use the status families and event names defined in `docs/PRD.md`; do not invent synonyms in APIs or UI labels. A transaction that is missing required provenance is `INCOMPLETE`, not fully auditable. A failed integrity check is `TAMPERED` or `FAILED` according to the verifier result, never silently `COMPLETED`.

## Stop conditions

Stop and ask for direction when a change would:

- require real patient data or production EHR access;
- move an LLM onto the alert-firing path;
- persist hidden reasoning or raw PHI in the immutable store;
- change the research question, primary metric, or J-BHI contribution claim;
- expand from the first transaction into multi-tenant, multi-organization, or regulatory product work.

Docs-only changes do not require runtime verification. Runtime and browser changes must follow the existing IronBee DevTools rule and be verified against the running system before completion.

