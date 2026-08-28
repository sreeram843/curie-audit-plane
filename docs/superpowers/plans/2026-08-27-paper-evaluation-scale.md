# Paper Evaluation Scale Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the synthetic evaluation from one repeated fixture into a configurable cohort study with reproducible aggregates and uncertainty summaries.

**Architecture:** Generate isolated synthetic FHIR bundles by deterministic identifier substitution, run the existing pipeline and verifier over each bundle, and aggregate case-level metrics without storing raw payloads in the report. Keep the existing single-transaction benchmark as the fast default test path and add a cohort mode for paper experiments.

**Tech Stack:** Python standard library, existing FHIR loader/pipeline/verifier, pytest, JSON/CSV report artifacts.

**Spec:** `docs/research-plan.md` and `docs/PRD.md` evaluation sections.

## Global Constraints

- Synthetic FHIR only; no real patient data or production EHR access.
- Default cohort size is 50; CLI accepts 1–1,000 encounters and rejects values outside that range.
- Cohort identifiers and timestamps are deterministic; report timing remains measured runtime data.
- Use medians/means and 95% confidence intervals for repeated numeric measurements.
- Human-review success remains a scripted proxy until an approved usability study exists.
- Preserve the existing single-transaction benchmark and report schema compatibility.

### Task 1: Generate deterministic synthetic cohorts

**Files:** `src/curie_audit_plane/evaluation/cohort.py`, `tests/evaluation/test_cohort.py`, `src/curie_audit_plane/adapters/llm_stub.py`, `src/curie_audit_plane/adapters/completion.py`

- [x] Test identifier substitution across FHIR references and deterministic output.
- [x] Run the cohort tests RED.
- [x] Implement bounded cohort generation and dynamic evidence references while preserving base-fixture output.
- [x] Run the cohort tests GREEN.

### Task 2: Aggregate repeated metrics

**Files:** `src/curie_audit_plane/evaluation/study.py`, `tests/evaluation/test_study.py`

- [x] Test cohort count, per-run observations, aggregate fractions, median timing, and 95% intervals.
- [x] Run the study tests RED.
- [x] Implement cohort execution, independent verification, evidence/human-action metrics, and confidence intervals using standard-library statistics.
- [x] Run the study tests GREEN.

### Task 3: Connect CLI and report artifacts

**Files:** `src/curie_audit_plane/cli.py`, `src/curie_audit_plane/evaluation/report.py`, `tests/test_cli.py`, `README.md`, `docs/research-plan.md`

- [x] Test `--encounters` and `--repetitions`, invalid bounds, and cohort metadata in JSON/CSV.
- [x] Run CLI tests RED.
- [x] Implement scaled evaluation output while retaining the existing default command contract.
- [x] Run CLI tests GREEN.

### Task 4: Verify and document

- [x] Run full backend tests with temporary coverage output and Ruff.
- [x] Run the evaluation command at the default cohort size and inspect JSON/CSV structure.
- [x] Document that synthetic cohort results validate auditability and overhead behavior, not clinical efficacy or deployment readiness.
