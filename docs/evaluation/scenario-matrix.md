# Evaluation scenario matrix protocol

## Purpose

This protocol evaluates workflow coverage for reconstructability across one bounded
synthetic FHIR-to-LLM transaction. It tests whether the audit plane records the
inputs, transformations, model execution, evidence, guardrails, human disposition,
replay, and access activity needed to inspect that transaction. It does not measure
clinical accuracy, diagnostic performance, treatment quality, or safety efficacy.

The research-question labels below refer to `docs/research-plan.md`:

- **RQ1 — reconstructability:** reconstruction of the required transaction record.
- **RQ2 — tamper detection:** detection of mutations and invalid integrity proofs.
- **RQ3 — overhead:** latency and storage overhead of complete capture.
- **RQ4 — reviewer UI:** reviewer identification of evidence, uncertainty,
  guardrail failures, and disposition.
- **RQ5 — replay fidelity:** deterministic-stub and hosted-model replay fidelity.

RQ2 is evaluated by the separate mutation suite, and RQ3 by cohort runs. They are
not inferred from scenario-arm outcomes. RQ4 outcomes in this matrix are
`SCRIPTED_PROXY` evidence only, not results from a human-subject usability study.

## Protocol arms

| Arm | Exercised seam | Expected stub outcome | RQ support |
|---|---|---|---|
| `accept` | Run a clean transaction with an immediate ACCEPT disposition. | Transaction is `COMPLETED`, required provenance is present, and ARC is complete. | RQ1 |
| `modify` | Run a clean transaction with an immediate MODIFY disposition. | Transaction is `COMPLETED` and the terminal human action is `MODIFY`. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `reject` | Run a clean transaction with an immediate REJECT disposition. | Transaction is `COMPLETED` and the terminal human action is `REJECT`. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `guardrail_warn` | Force a WARN guardrail result before ACCEPT. | WARN is recorded and the accepted transaction is `COMPLETED`. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `guardrail_block` | Force a BLOCK guardrail result without an override or human action. | Transaction remains pending/blocked and verification is `INCOMPLETE` by design. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `synthea_sliced` | Slice the first discoverable Synthea patient bundle to one encounter. | Transaction is `COMPLETED`, or the arm is `NOT_AVAILABLE` when no eligible external bundle exists. | RQ1 |
| `two_step_accept` | Call `run_transaction()` without a human action, then `record_human_action(ACCEPT)`. | Initial status is `WAITING_FOR_REVIEW`; final status is `COMPLETED` with complete ARC. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `block_override_accept` | Force BLOCK and provide `override_policy_version="override.v1"` with ACCEPT. | Transaction is `COMPLETED`; the human-action record includes the override policy version. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `natural_guardrail_warn` | Inject controlled output containing `TEST-00001` and cited evidence, without calling the live provider, then ACCEPT. | `phi_scan.v1` records WARN, `evidence_refs.v1` records PASS, and the transaction is `COMPLETED` / `VERIFIED`. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `natural_guardrail_block` | Inject controlled output whose findings lack evidence citations, without calling the live provider; record no human action. | `evidence_refs.v1` blocks the output, the transaction is blocked, ARC is incomplete, and verification is `INCOMPLETE`. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `provider_failure` | Replace the completer with one that raises `RuntimeError`. | Transaction is `FAILED`, a `TRANSACTION_FAILED` event is recorded, and status does not remain `RUNNING`. | RQ1 |
| `sparse_encounter` | Use a temporary Patient-and-Encounter-only synthetic bundle, then ACCEPT. | Transaction is `COMPLETED`, its `subject_ref` identifies the sparse Patient, and structured missing-data information remains present. | RQ1 |
| `synthea_sliced_second` | Slice the second discoverable Synthea patient bundle to one encounter. | Transaction is `COMPLETED` with a different subject from the first Synthea arm, or `NOT_AVAILABLE`. | RQ1 |
| `modify_evidence` | Record MODIFY with evidence references different from the model output. | Transaction is `COMPLETED`; terminal action is `MODIFY`; replacement evidence references differ from the source; and the final-output digest differs from the source-output digest. | RQ1, RQ4 (`SCRIPTED_PROXY`) |
| `replay_substitution` | ACCEPT, then replay with `prompt_version="clinical-summary.v2"`. | Replay is `DIVERGENT` because the prompt version changed, `REPLAY_RECORDED` appears in the access stream, and the sealed clinical record remains `VERIFIED`. | RQ1, RQ5 |
| `access_audit` | ACCEPT, record an export access, then replay. | At least two access events are recorded while the sealed clinical chain remains unchanged and `VERIFIED`. | RQ1 |

## Commands

Run the scenario matrix with a single encounter and repetition:

```bash
curie-audit-plane evaluate --output-dir evaluation-results-scenarios --encounters 1 --repetitions 1
```

Select either `CAP_LLM_PROVIDER=stub` or
`CAP_LLM_PROVIDER=openai_compatible`. Never write stub and live-provider runs to
the same output directory.

An optional slower confidence-interval run is:

```bash
curie-audit-plane evaluate --encounters 50 --repetitions 3 --output-dir evaluation-results-openai-compatible-r3
```

## Result artifacts

Each output directory contains:

- `evaluation-report.json`, schema `curie-evaluation.v1.1`, the authoritative structured report;
- `evaluation-metrics.csv`, tabular cohort, benchmark, and scenario rows; and
- `evaluation-cohort-metrics.svg`, the vector cohort figure.

Keep the established 50-encounter stub artifacts in `evaluation-results/` and the
established 50-encounter live-provider artifacts in
`evaluation-results-openai-compatible/`. The 16-arm protocol in this document
uses `evaluation-results-scenarios/`. Do not overwrite or combine these
directories when changing providers, encounter counts, or repetition counts.

## Measured results

Recorded 2026-08-28 from `CAP_LLM_PROVIDER=openai_compatible`
(`medgemma-4b-it-mlx` at the local OpenAI-compatible endpoint) via:

```bash
curie-audit-plane evaluate --output-dir evaluation-results-scenarios --encounters 1 --repetitions 1
```

The authoritative `generated_at` stamp is `2026-08-28T13:25:55.938220+00:00` in
`evaluation-results-scenarios/evaluation-report.json`. Do not transcribe model
summaries or FHIR payloads. In this run `natural_guardrail_warn` recorded
`phi_scan.v1=WARN`, `evidence_refs.v1=PASS`, and `uncertainty.v1=PASS`.

| Arm | Status | Human action | ARC | Verification | Subject reference | Replay result | Access-event count |
|---|---|---|---|---|---|---|---|
| `accept` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `modify` | `COMPLETED` | `MODIFY` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `reject` | `COMPLETED` | `REJECT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `guardrail_warn` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `guardrail_block` | `BLOCKED` | `PENDING` | `0.7` | `INCOMPLETE` | opaque token | `null` | `null` |
| `synthea_sliced` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `two_step_accept` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `block_override_accept` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `natural_guardrail_warn` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `natural_guardrail_block` | `BLOCKED` | `PENDING` | `0.65` | `INCOMPLETE` | opaque token | `null` | `null` |
| `provider_failure` | `FAILED` | `PENDING` | `0.4` | `INCOMPLETE` | opaque token | `null` | `null` |
| `sparse_encounter` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `synthea_sliced_second` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `modify_evidence` | `COMPLETED` | `MODIFY` | `1.0` | `VERIFIED` | opaque token | `null` | `null` |
| `replay_substitution` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `DIVERGENT` | `null` |
| `access_audit` | `COMPLETED` | `ACCEPT` | `1.0` | `VERIFIED` | opaque token | `null` | `2` |

## Limitations and interpretation

- A 50-encounter cohort produced by cloning and rewriting one fixture is not 50
  independent patients and must not be interpreted as clinical population
  evidence.
- Hosted same-prompt replay is at best `EQUIVALENT` and never `EXACT_MATCH`.
  This 1×1 live cohort classified same-prompt replay as `DIVERGENT`. The
  scenario-arm `replay_substitution` result `DIVERGENT` is caused by changing
  `prompt_version` to `clinical-summary.v2`, not by hosted nondeterminism.
- Reviewer-task evidence remains `SCRIPTED_PROXY`. The matrix does not establish
  human usability or reviewer task success.
- Synthea source bundles are external and are not committed to this repository.
  Discovery requires a Patient identifier system of
  `https://github.com/synthetichealth/synthea`. Either Synthea arm may report
  `NOT_AVAILABLE` when its required source is absent.
- BLOCK without an explicit override is intentionally incomplete because the
  workflow cannot reach a terminal human disposition.
- Natural guardrail arms inject controlled structured output through a stub
  wrapper so they exercise the real guardrail engine without calling the live
  provider for those arms. The original completer is restored after each arm.
- Scenario outcomes support workflow coverage only. RQ2 requires the independent
  mutation suite, RQ3 requires fixed cohort configurations, and publication claims
  require rerunning all measurements from versioned artifacts.
