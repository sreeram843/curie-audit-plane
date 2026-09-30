# Prototype TDD evidence

**Source plan:** `docs/superpowers/plans/2026-08-27-curie-audit-plane-prototype.md`

## User journeys

- As a reviewer, I can inspect a synthetic FHIR-to-LLM transaction and record ACCEPT, MODIFY, or REJECT.
- As an investigator, I can detect mutated, deleted, reordered, or falsely signed events.
- As a researcher, I can measure Audit Reconstruction Completeness on a clean fixture.

## Guarantees

| # | What is guaranteed | Test | Type | Result |
|---|---|---|---|---|
| 1 | Event types and statuses match the PRD; rationale has no hidden-reasoning field | `tests/unit/test_event_contract.py` | unit | PASS |
| 2 | Canonical JSON hashing is stable and omits `event_hash` | `tests/unit/test_canonical_hash.py` | unit | PASS |
| 3 | Chain, Merkle, and Ed25519 detect mutation, deletion, reorder, bad proof, and bad signature | `tests/unit/test_verifier_tamper.py` | unit | PASS |
| 4 | Protected store round-trips by SHA-256; audit metadata rejects clinical keys | `tests/unit/test_content_store.py` | unit | PASS |
| 5 | Synthetic bundle produces input manifests, transforms, stub output, guardrails, and human actions | `tests/integration/test_full_transaction.py` | integration | PASS |
| 6 | API run/verify/export/sankey/review work | `tests/integration/test_api.py` | integration | PASS |
| 7 | Clean ARC ≥ 95% with 100% tamper detection and 0% false tamper | `tests/evaluation/test_benchmark.py` | evaluation | PASS |
| 8 | Console status labels, filters, Sankey stage IDs, review/verify/replay, and downloads | `console/src/viewModel.test.ts`, `console/src/App.test.tsx` | unit | PASS |
| 9 | Local OpenAI-compatible adapter records LM Studio model/endpoint and rejects hidden-reasoning fields | `tests/unit/test_openai_compatible.py` | unit | PASS |
| 10 | PENDING cannot be a terminal human disposition | `tests/integration/test_api.py`, `tests/integration/test_full_transaction.py` | integration | PASS |
| 11 | Fail-closed bearer auth, roles, and digest-checked content access | `tests/integration/test_api.py` | integration | PASS |
| 12 | Access-audit stream does not unseal the clinical proof | `tests/integration/test_api.py`, `tests/unit/test_verifier_tamper.py` | unit/integration | PASS |
| 13 | Transformation events carry the full TransformationRecord | `tests/integration/test_full_transaction.py` | integration | PASS |
| 14 | Guardrail scopes are explicit and unchecked scopes are omitted | `tests/unit/test_guardrails.py` | unit | PASS |
| 15 | Merkle proof fields, key identity, and post-seal appends are verified | `tests/unit/test_verifier_tamper.py` | unit | PASS |
| 16 | Terminal failures emit TRANSACTION_FAILED and leave FAILED, not RUNNING | `tests/integration/test_full_transaction.py` | integration | PASS |
| 17 | Replay classifies exact, equivalent, and divergent | `tests/unit/test_replay.py` | unit | PASS |
| 18 | Research export excludes identifiers and protected payloads | `tests/unit/test_research_export.py` | unit | PASS |
| 19 | FHIR AuditEvent.subtype is a CodeableConcept; Provenance uses manifest resource types | `tests/unit/test_fhir_projection.py` | unit | PASS |
| 20 | Evaluation report emits versioned JSON/CSV metrics, case outcomes, denominators, and explicit scripted-study status | `tests/evaluation/test_report.py`, `tests/test_cli.py` | evaluation/integration | PASS |
| 21 | Synthetic cohort generation is deterministic, bounded to 1–1,000 encounters, and rewrites identifiers, references, and timestamps without changing the fixture shape | `tests/evaluation/test_cohort.py` | evaluation | PASS |
| 22 | Repeated cohort study runs the real pipeline plus an independent verifier and emits mean, median, 95% CI, CSV rows, and a vector figure | `tests/evaluation/test_study.py`, `tests/evaluation/test_figure.py`, `tests/test_cli.py` | evaluation/integration | PASS |
| 23 | Scenario matrix covers two-step review, override ACCEPT, natural WARN/BLOCK, provider failure, sparse encounter, Synthea slices, evidence MODIFY, replay substitution, and access-audit | `tests/evaluation/test_scenarios.py` | evaluation | PASS |

## Coverage

`pytest` with `--cov=curie_audit_plane --cov-fail-under=80` reported **94.59%** on 2026-08-28 (146 tests). The reproducible evaluation command is `curie-audit-plane evaluate --output-dir evaluation-results --encounters 50 --repetitions 1`; it writes `evaluation-report.json`, `evaluation-metrics.csv`, and `evaluation-cohort-metrics.svg`. Console Vitest covers view-model stage mapping plus App selection, ACCEPT/MODIFY/REJECT, verify, replay, filters, JSON modes, downloads, Sankey, evidence, and keyboard timeline controls.

The evaluation report marks scripted reviewer reconstruction as `SCRIPTED_PROXY`; it is not a human-subject usability result. Baseline, overhead, replay, and integrity results are prototype measurements over synthetic fixtures and must be rerun with fixed experiment configurations before a paper submission.

## RED/GREEN

- Contract and hashing tests failed on missing modules, then passed after enums, rationale schema, and canonical SHA-256 were added.
- Integrity and store tests failed on missing modules, then passed after chain/Merkle/Ed25519/verifier/SQLite/file-store implementation.
- Pipeline and API tests failed until the orchestrator, FastAPI, and SQLite `check_same_thread=False` were in place.
