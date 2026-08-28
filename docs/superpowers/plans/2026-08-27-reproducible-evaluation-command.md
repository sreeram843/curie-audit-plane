# Reproducible Paper Evaluation Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one reproducible command that runs the implemented synthetic benchmark and emits machine-readable JSON and CSV results for the paper evaluation package.

**Architecture:** Reuse the existing `Pipeline`, `run_benchmark`, ARC field definitions, and verifier. Add a small evaluation-report layer that records metric values, denominators, case-level outcomes, and explicit availability states for metrics that require baselines or human-study data. Keep protected clinical payloads out of report artifacts.

**Tech Stack:** Python 3.11+, dataclasses, JSON/CSV standard library modules, pytest, Ruff, existing deterministic stub pipeline.

**Spec:** `docs/research-plan.md` and `docs/PRD.md` evaluation sections.

## Global Constraints

- Use synthetic FHIR fixtures only; do not add real patient data.
- Do not write raw clinical payloads, prompts, tokens, or signing keys into reports.
- Keep the initial runner local and deterministic; hosted-model and human-review measurements remain explicit unavailable metrics until their data sources exist.
- Preserve existing `run_benchmark` behavior and CLI compatibility.
- Every report must include numerator, denominator, formula, status, and source/configuration metadata where applicable.

### Task 1: Define report schema and failing tests

**Files:**
- Create: `src/curie_audit_plane/evaluation/report.py`
- Create: `tests/evaluation/test_report.py`

**Interfaces:**
- Produces `EvaluationReport`, `MetricResult`, and `build_evaluation_report(pipeline)`. `MetricResult` includes `name`, `value`, `numerator`, `denominator`, `unit`, `status`, and `notes`.

- [ ] **Step 1: Write the failing test**

  Test that a report contains ARC, required-event completeness, tamper detection, false tamper rate, and replay fidelity with numeric denominators; unavailable overhead and reviewer metrics have status `NOT_AVAILABLE` and do not invent values.

- [ ] **Step 2: Run test to verify it fails**

  Run: `.venv/bin/pytest --no-cov tests/evaluation/test_report.py -q`

  Expected: FAIL because the report module does not exist.

- [ ] **Step 3: Implement the minimal report schema**

  Add typed dataclasses and a builder that adapts the existing `BenchmarkReport` without changing the benchmark mutation logic.

- [ ] **Step 4: Run test to verify it passes**

  Run: `.venv/bin/pytest --no-cov tests/evaluation/test_report.py -q`

  Expected: PASS.

- [ ] **Step 5: Commit**

  `git add src/curie_audit_plane/evaluation/report.py tests/evaluation/test_report.py && git commit -m "test: define reproducible evaluation report"`

### Task 2: Add JSON and CSV serialization

**Files:**
- Modify: `src/curie_audit_plane/evaluation/report.py`
- Modify: `tests/evaluation/test_report.py`

**Interfaces:**
- `EvaluationReport.to_json_dict()` returns only JSON-safe metadata and metrics.
- `EvaluationReport.to_csv_rows()` returns one row per metric plus case-level rows in a separate case schema.

- [ ] **Step 1: Write the failing test**

  Test JSON round-trip, stable metric ordering, CSV headers, case-level mutation names, and absence of payload fields such as `bounded_context` or raw content.

- [ ] **Step 2: Run test to verify it fails**

  Run: `.venv/bin/pytest --no-cov tests/evaluation/test_report.py -q`

  Expected: FAIL on missing serializers or incomplete fields.

- [ ] **Step 3: Implement standard-library serializers**

  Serialize to a versioned report object with `generated_at`, `fixture`, `model_runtime`, `metrics`, and `cases`; serialize CSV using `csv.DictWriter` with deterministic columns.

- [ ] **Step 4: Run test to verify it passes**

  Run: `.venv/bin/pytest --no-cov tests/evaluation/test_report.py -q`

  Expected: PASS.

- [ ] **Step 5: Commit**

  `git add src/curie_audit_plane/evaluation/report.py tests/evaluation/test_report.py && git commit -m "feat: serialize paper evaluation reports"`

### Task 3: Expose a CLI evaluation command

**Files:**
- Modify: `src/curie_audit_plane/cli.py`
- Modify: `tests/test_cli.py` or the existing CLI test file after locating it
- Modify: `README.md`

**Interfaces:**
- Add `curie-audit-plane evaluate --output-dir <path>`.
- Write `evaluation-report.json` and `evaluation-metrics.csv` under the requested directory.
- Print a concise summary with metric values and paths; never print secrets.

- [ ] **Step 1: Write the failing test**

  Test that an isolated temporary output directory receives both files, the command exits successfully, and the JSON contains the same benchmark values as `build_evaluation_report`.

- [ ] **Step 2: Run test to verify it fails**

  Run: `.venv/bin/pytest --no-cov tests/test_cli.py -q`

  Expected: FAIL because the evaluate command is not registered.

- [ ] **Step 3: Implement the CLI command**

  Construct the configured local pipeline using existing CLI setup helpers, run the deterministic benchmark, create the report, and write only the two requested artifacts. Ensure parent directories are created without deleting existing files.

- [ ] **Step 4: Run test to verify it passes**

  Run: `.venv/bin/pytest --no-cov tests/test_cli.py -q`

  Expected: PASS.

- [ ] **Step 5: Commit**

  `git add src/curie_audit_plane/cli.py tests/test_cli.py README.md && git commit -m "feat: add reproducible evaluation command"`

### Task 4: Verify the complete evaluation path

**Files:**
- Modify: `docs/testing/prototype.tdd.md`

- [ ] **Step 1: Run focused report and CLI tests**

  Run: `.venv/bin/pytest --no-cov tests/evaluation/test_report.py tests/test_cli.py -q`

- [ ] **Step 2: Run the command against a temporary output directory**

  Run: `tmpdir=$(mktemp -d) && .venv/bin/curie-audit-plane evaluate --output-dir "$tmpdir" && .venv/bin/python -m json.tool "$tmpdir/evaluation-report.json" >/dev/null`

- [ ] **Step 3: Run full backend quality gates**

  Run: `.venv/bin/pytest -q` and `.venv/bin/ruff check --no-cache src tests`.

- [ ] **Step 4: Document evidence and explicit gaps**

  Record the command, generated metrics, and the fact that overhead, baseline comparison, and reviewer-task metrics remain `NOT_AVAILABLE` until their data collection is implemented.

- [ ] **Step 5: Commit**

  `git add docs/testing/prototype.tdd.md && git commit -m "docs: record evaluation runner evidence"`

## Self-review checklist

- The report does not claim independent ARC verification unless the verifier is actually invoked for the relevant field set.
- The denominator for every numeric metric is visible.
- Clean, tampered, replay, and unavailable metrics are distinguishable.
- Report artifacts contain no raw FHIR resources, content payloads, prompts, tokens, or private keys.
- The command is deterministic for the stub and does not require network access.
