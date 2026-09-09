# Evaluation Scenario Matrix Implementation Plan

**Superseded artifact paths:** scenario rows are published inside
`evaluation-results/` and `evaluation-results-openai-compatible/`. Do not create
`evaluation-results-scenarios/`. The live protocol is
`docs/evaluation/scenario-matrix.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `evaluate` with every remaining prototype workflow arm that changes an audit metric, then record stub and live results without claiming clinical efficacy or human-subject usability.

**Architecture:** Keep one `run_scenario_matrix(pipeline)` that temporarily swaps fixture, completer, or review path, then restores them. Reuse `Pipeline.run_transaction`, `record_human_action`, `replay`, and `record_access`. Emit one `row_type=scenario` CSV row per arm. Document expected vs measured outcomes in `docs/evaluation/scenario-matrix.md` pointing at versioned `--output-dir` artifacts. Do not add a scenario framework, extra LLM providers, or MIMIC/Challenge loaders.

**Tech Stack:** Existing pytest, Pipeline, stub/openai-compatible completers, JSON/CSV evaluation report.

**Spec:** `docs/research-plan.md` RQs 1–5, `docs/PRD.md` prototype-complete items 5, 9, 10, 16, 24, `docs/jbhi-submission-requirements.md` minimum evaluation package.

## Global Constraints

- Synthetic FHIR only; Synthea stays on `CURIE_SYNTHEA_BUNDLE` / sibling `curie-prediction-pipeline/data/synthea/fhir`; never copy those dumps into this repo.
- Do not change the research question, primary metric (ARC), or J-BHI contribution claim.
- Do not persist hidden chain-of-thought or raw PHI in the immutable audit store or report JSON.
- Forced `force_guardrail` arms stay; new arms must also exercise the real guardrail engine and the two-step review API.
- Natural guardrail and provider-failure arms wrap `pipeline.completer` and restore it in `finally`, so live evaluate does not depend on MedGemma emitting `TEST-#####`.
- Hosted replay remains at best `EQUIVALENT`, never `EXACT_MATCH`.
- Reviewer-task metric stays `SCRIPTED_PROXY`. Do not add an IRB human study.
- Skip: bigger N on cloned identifiers, full MIMIC, Challenge 2019 as clinical accuracy, multi-tenant, production EHR.
- Do not commit unless the user asks. Plan steps that say commit are optional.

## In scope (16 arms)

Already in `run_scenario_matrix` (keep):

| name | what it proves |
|---|---|
| `accept` | clean COMPLETED + ARC 1.0 |
| `modify` | MODIFY terminal disposition |
| `reject` | REJECT terminal disposition |
| `guardrail_warn` | forced WARN still COMPLETED |
| `guardrail_block` | forced BLOCK stays PENDING / INCOMPLETE |
| `synthea_sliced` | first sliced Synthea encounter, or `NOT_AVAILABLE` |

Add:

| name | seam | expected (stub) |
|---|---|---|
| `two_step_accept` | `run_transaction()` then `record_human_action(ACCEPT)` | first status `WAITING_FOR_REVIEW`; final `COMPLETED` / ARC 1.0 |
| `block_override_accept` | `force_guardrail=BLOCK` + `override_policy_version="override.v1"` | `COMPLETED`; human event includes override version |
| `natural_guardrail_warn` | completer output contains `TEST-00001`; ACCEPT | `GUARDRAIL_COMPLETED` with `rule_id=phi_scan.v1` and `WARN`; transaction `COMPLETED` |
| `natural_guardrail_block` | findings with no evidence citations; no human action | `BLOCKED`; `evidence_refs.v1` BLOCK; ARC &lt; 1.0; verification `INCOMPLETE` |
| `provider_failure` | completer raises `RuntimeError` | `FAILED`; `TRANSACTION_FAILED`; not `RUNNING` |
| `sparse_encounter` | Patient+Encounter-only temp bundle; ACCEPT | `COMPLETED`; `subject_ref` from that Patient; missing_data still present |
| `synthea_sliced_second` | second Synthea patient JSON if present | `COMPLETED` with a different `subject_ref` than the first Synthea arm, or `NOT_AVAILABLE` |
| `modify_evidence` | MODIFY with different `evidence_references` than the model output | `COMPLETED`; `final_output_digest` ≠ source output digest |
| `replay_substitution` | `replay(..., prompt_version="clinical-summary.v2")` after ACCEPT | stub: `DIVERGENT`; access stream has `REPLAY_RECORDED`; clinical verification still `VERIFIED` |
| `access_audit` | ACCEPT, then `record_access` export, then `replay` | ≥2 access events; clinical chain unchanged / `VERIFIED` |

Out of scenario matrix (document only, run as CLI):

- Live `--encounters 50 --repetitions 3` for latency/storage CIs (not new arms).
- Tamper suite, hash-only / FHIR Provenance baselines (already in benchmark/harness).

## File map

- Modify: `src/curie_audit_plane/evaluation/scenarios.py` — all new arms; completer wrap helpers; Synthea multi-file discovery.
- Modify: `src/curie_audit_plane/pipeline.py` — optional `prompt_version` / `model_id` on `replay()`.
- Modify: `tests/evaluation/test_scenarios.py` — matrix assertions for new names and qualitative outcomes.
- Modify: `tests/evaluation/test_report.py` — CSV `row_type=scenario` names include the new arms.
- Modify: `tests/unit/test_replay.py` or `tests/integration/test_full_transaction.py` — replay substitution kwargs.
- Create: `docs/evaluation/scenario-matrix.md` — protocol, expected table, result pointers, limitations.
- Modify: `docs/research-plan.md` — point at the scenario matrix and result dirs.
- Modify: `docs/testing/prototype.tdd.md` — guarantee row for the matrix.
- Write (after runs, not hand-authored numbers): `evaluation-results-scenarios/` stub-or-live 1-encounter artifacts; optional `evaluation-results-openai-compatible-r3/` for 50×3. Do not overwrite `evaluation-results/` (stub 50).

---

### Task 1: Replay substitution kwargs

**Files:**
- Modify: `src/curie_audit_plane/pipeline.py` (`replay`)
- Test: `tests/unit/test_replay.py` or `tests/integration/test_full_transaction.py`

**Interfaces:**
- Consumes: existing `Pipeline.replay(transaction_id, actor=..., role=...)`
- Produces: `replay(self, transaction_id: str, *, actor: str = ..., role: str = ..., prompt_version: str | None = None, model_id: str | None = None) -> ReplayClassification`

- [ ] **Step 1: Write the failing test**

```python
def test_replay_with_prompt_v2_is_divergent_on_stub(tmp_path):
    pipeline = _pipeline(tmp_path)
    result = pipeline.run_transaction(
        human_action=HumanActionStatus.ACCEPT,
        actor="reviewer@curie.local",
        prompt_version="clinical-summary.v1",
    )
    replayed = pipeline.replay(
        result.transaction.transaction_id,
        prompt_version="clinical-summary.v2",
    )
    assert replayed.result == "DIVERGENT"
    assert "summary differs" in replayed.reasons
    access = pipeline.services.audit.list_access_events(result.transaction.transaction_id)
    assert any(event.event_type.value == "replay.recorded" for event in access)
    loaded = pipeline.load_result(result.transaction.transaction_id)
    assert loaded.verification.status == VerificationStatus.VERIFIED
    pipeline.close()
```

Use the real `EventType.REPLAY_RECORDED` enum value from `models/enums.py` rather than a guessed string.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest -q tests/integration/test_full_transaction.py::test_replay_with_prompt_v2_is_divergent_on_stub`
Expected: FAIL (`replay()` unexpected keyword `prompt_version`).

- [ ] **Step 3: Write minimal implementation**

In `Pipeline.replay`, after reading `prompt_version` / `model_id` from `MODEL_REQUESTED`, if the kwargs are not `None`, use the kwargs. Pass those values into `CompletionRequest`. Keep `_completer_for_replay(model_event)` so stub transactions still replay on the stub.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest -q tests/integration/test_full_transaction.py::test_replay_with_prompt_v2_is_divergent_on_stub tests/unit/test_replay.py`
Expected: PASS. Existing same-config stub replay stays `EXACT_MATCH`.

---

### Task 2: Expand scenario matrix tests (RED)

**Files:**
- Test: `tests/evaluation/test_scenarios.py`
- Test: `tests/evaluation/test_report.py`

**Interfaces:**
- Consumes: `run_scenario_matrix(pipeline) -> dict[str, object]` with key `"scenarios": list[dict]`
- Produces: assertions on the 16 names and the qualitative outcomes in the in-scope table

- [ ] **Step 1: Extend `test_scenario_matrix_covers_review_and_guardrail_arms`**

Rename to `test_scenario_matrix_covers_workflow_arms` or add a second test. Required names:

```python
REQUIRED = {
    "accept", "modify", "reject", "guardrail_warn", "guardrail_block",
    "synthea_sliced", "two_step_accept", "block_override_accept",
    "natural_guardrail_warn", "natural_guardrail_block", "provider_failure",
    "sparse_encounter", "synthea_sliced_second", "modify_evidence",
    "replay_substitution", "access_audit",
}
assert {item["name"] for item in report["scenarios"]} >= REQUIRED
```

Qualitative checks (use `by_name[...]`):

- `two_step_accept`: `transaction_status == COMPLETED`, notes mention `WAITING_FOR_REVIEW` or a `waiting_status` field.
- `block_override_accept`: `COMPLETED`, `human_action == ACCEPT`, notes or payload field `override.v1`.
- `natural_guardrail_warn`: `COMPLETED`; notes or a `guardrail_rule_ids` list includes `phi_scan.v1`.
- `natural_guardrail_block`: `BLOCKED`, `arc < 1.0`.
- `provider_failure`: `FAILED`.
- `sparse_encounter`: `COMPLETED`; `subject_ref` starts with `Patient/`.
- `modify_evidence`: `MODIFY`; notes mention digest change or `source_output_digest != final`.
- `replay_substitution`: notes or `replay_result == DIVERGENT` on stub.
- `access_audit`: `access_event_count >= 2`.
- Synthea second: if `status != NOT_AVAILABLE`, `subject_ref` differs from `synthea_sliced`.

Extend `_observation` in the implementation task to carry `waiting_status`, `override_policy_version`, `guardrail_rule_ids`, `replay_result`, `access_event_count`, `source_output_digest`, `final_output_digest` so tests do not parse free-text notes.

CSV test: `{row["name"] for row in rows if row["row_type"] == "scenario"} >= REQUIRED`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest -q tests/evaluation/test_scenarios.py tests/evaluation/test_report.py`
Expected: FAIL on missing scenario names.

Do not implement production code in this task.

---

### Task 3: Implement remaining arms (GREEN)

**Files:**
- Modify: `src/curie_audit_plane/evaluation/scenarios.py`
- Modify: `src/curie_audit_plane/evaluation/encounter_slice.py` only if sparse bundles need a tiny helper; prefer inline JSON in `scenarios.py`.

**Interfaces:**
- Consumes: `Pipeline.run_transaction`, `record_human_action`, `replay`, `record_access`, `complete_stub` / current `pipeline.completer`
- Produces: 16 scenario dicts; `discover_synthea_bundles() -> list[Path]` (patient JSON only; skip `*Information*.json`)

- [ ] **Step 1: Completer wrap helpers in `scenarios.py`**

```python
from curie_audit_plane.adapters.completion import Completer, CompletionRequest, CompletionResult
from curie_audit_plane.integrity.hashing import sha256_hex
from curie_audit_plane.integrity.canonical import canonicalize

def _with_output(inner: Completer, output: StructuredRationale) -> Completer:
    def completer(request: CompletionRequest) -> CompletionResult:
        result = inner(request)
        payload = canonicalize(output.model_dump(mode="json"))
        return CompletionResult(
            output=output,
            manifest=result.manifest,
            request_digest=result.request_digest,
            response_digest=sha256_hex(payload),
            token_usage=result.token_usage,
        )
    return completer

def _boom(_request: CompletionRequest) -> CompletionResult:
    raise RuntimeError("scenario provider failure")
```

PHI warn output: copy stub fields but set `summary` to include `TEST-00001` (the existing `phi_scan.v1` regex). Natural block output: one `Finding(text="Unsupported claim", evidence_refs=[])` and `evidence_references=[]`. Keep structured-rationale fields; no hidden-reasoning keys.

Restore `pipeline.completer` in `try`/`finally` around each wrap.

- [ ] **Step 2: Two-step, override, sparse, modify-evidence, access, replay**

- `two_step_accept`: `waiting = pipeline.run_transaction(actor=...)` (no `human_action`); record `waiting.transaction.status`; then `record_human_action(..., ACCEPT)`.
- `block_override_accept`: `run_transaction(human_action=ACCEPT, force_guardrail=BLOCK, override_policy_version="override.v1")`.
- `sparse_encounter`: write a temp Bundle with Patient `id=sparse-1` and one Encounter; set `pipeline.fixture_path`; ACCEPT; unlink.
- `modify_evidence`: first run ACCEPT (or reuse stub output ids), MODIFY with `evidence_references=["cond-htn-TEST-00001"]` only if that differs from the model list; compare digests from the human event vs `STRUCTURED_OUTPUT_VALIDATED`.
- `access_audit`: ACCEPT, `record_access(..., action="export", endpoint="export")`, `replay(transaction_id)`; count `list_access_events`.
- `replay_substitution`: ACCEPT then `replay(..., prompt_version="clinical-summary.v2")`; store `replay_result`.

- [ ] **Step 3: Synthea second file**

Replace `discover_synthea_bundle()` with `discover_synthea_bundles() -> list[Path]` that returns sorted patient JSON paths. First path → existing `synthea_sliced`. Second path → `synthea_sliced_second`. If fewer than 2 files, second arm is `status: NOT_AVAILABLE` with a notes string. Slice with `slice_first_encounter`; temp file; do not copy into git.

- [ ] **Step 4: Run tests GREEN**

Run: `.venv/bin/ruff check src/curie_audit_plane/evaluation/scenarios.py src/curie_audit_plane/pipeline.py tests/evaluation`
Run: `.venv/bin/pytest -q --cov=curie_audit_plane --cov-fail-under=80`
Expected: all pass, coverage ≥ 80%.

---

### Task 4: Document protocol (before live numbers)

**Files:**
- Create: `docs/evaluation/scenario-matrix.md`
- Modify: `docs/research-plan.md` (Current prototype evaluation command)
- Modify: `docs/testing/prototype.tdd.md`

- [ ] **Step 1: Write `docs/evaluation/scenario-matrix.md`**

Must include:

1. Purpose: workflow coverage for reconstructability, not clinical accuracy.
2. The 16-arm table (name, seam, expected stub outcome, which RQ it supports).
3. Commands:

```bash
curie-audit-plane evaluate --output-dir evaluation-results-scenarios --encounters 1 --repetitions 1
# stub vs live: CAP_LLM_PROVIDER=stub | openai_compatible; never mix output dirs
# optional CI run (slow): --encounters 50 --repetitions 3 --output-dir evaluation-results-openai-compatible-r3
```

4. Result artifact paths and the rule: stub 50 stays in `evaluation-results/`; live 50 stays in `evaluation-results-openai-compatible/`; this matrix uses `evaluation-results-scenarios/`.
5. Limitations: 50 clones ≠ 50 patients; hosted replay `DIVERGENT`; `SCRIPTED_PROXY`; Synthea not in git; BLOCK without override is incomplete by design; natural guardrail arms wrap the completer.
6. Empty **Measured results** section with a table whose cells are filled in Task 5 from JSON (do not invent numbers here).

- [ ] **Step 2: Research plan + TDD evidence**

In `docs/research-plan.md`, add a short subsection that `evaluate` always runs the scenario matrix and that interpretation lives in `docs/evaluation/scenario-matrix.md`.

In `docs/testing/prototype.tdd.md`, add guarantee 23: scenario matrix covers two-step review, override ACCEPT, natural WARN/BLOCK, provider failure, sparse encounter, Synthea slices, evidence MODIFY, replay substitution, and access-audit; test `tests/evaluation/test_scenarios.py`.

---

### Task 5: Run and fill measured results

**Files:**
- Write: `evaluation-results-scenarios/evaluation-report.json` (and csv/svg)
- Modify: `docs/evaluation/scenario-matrix.md` Measured results table only

- [ ] **Step 1: Stub matrix (fast)**

If `.env` is `openai_compatible`, run with an explicit stub completer only if the CLI already uses settings. Prefer: temporarily document that unit tests are the stub oracle, then run live 1-encounter as the recorded live matrix.

Practical command (uses current `.env`):

```bash
.venv/bin/curie-audit-plane evaluate --output-dir evaluation-results-scenarios --encounters 1 --repetitions 1
```

Keep LM Studio up if `CAP_LLM_PROVIDER=openai_compatible`. Natural/provider arms must not require the model to cooperate (Task 3 wraps the completer).

- [ ] **Step 2: Fill the measured table from JSON**

Use the report’s `scenarios` list. Copy status, human_action, ARC, verification, opaque `subject_ref` tokens (raw Patient IDs stay in the protected identity map), replay_result, access_event_count. Do not paste model summaries or FHIR payloads into the doc.

- [ ] **Step 3: Optional 50×3 (only if user confirms time)**

```bash
.venv/bin/curie-audit-plane evaluate --output-dir evaluation-results-openai-compatible-r3 --encounters 50 --repetitions 3
```

Expect on the order of tens of minutes. Record cohort mean/median/CI for latency and storage in the same doc under **Cohort repetitions**, not as new scenario rows. Do not overwrite `evaluation-results/` or `evaluation-results-openai-compatible/`.

- [ ] **Step 4: Full verification**

Run: `.venv/bin/pytest -q --cov=curie_audit_plane --cov-fail-under=80`
Inspect that `evaluation-results-scenarios/evaluation-metrics.csv` has `row_type=scenario` for all 16 names.
No browser verification (docs + CLI artifacts only).

---

## Self-review

**Spec coverage**

- RQ1 reconstructability: two-step, sparse, failure, Synthea, BLOCK/INCOMPLETE.
- RQ2 tamper: already benchmark; not duplicated.
- RQ3 overhead: optional 50×3, not scenario rows.
- RQ4 reviewer UI: still `SCRIPTED_PROXY`; access-audit is provenance of investigator actions, not a human study.
- RQ5 replay: substitution arm + existing hosted `DIVERGENT`.
- PRD 5 two prompt configs: `replay_substitution`.
- PRD 9 override path: `block_override_accept`.
- PRD 10 ACCEPT/MODIFY/REJECT: already present; evidence MODIFY adds digest change.
- PRD 24 access/export: `access_audit`.
- J-BHI package: workflow coverage listed; baselines already in harness.

**Explicitly not in this plan:** MIMIC, Challenge 2019, human IRB, cloned N increase, retrieval-off flag (no existing seam), new UI.

**Placeholder scan:** none. Commit steps omitted as optional per user git rules.
