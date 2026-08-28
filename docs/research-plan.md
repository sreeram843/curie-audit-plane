# Curie Audit Plane Research Plan

## Research claim

The prototype will test whether a FHIR-to-LLM provenance plane can make the observable basis of a clinical AI transaction reconstructable and tamper-evident without storing hidden chain-of-thought or raw PHI in an immutable audit store.

This is an auditability and interoperability study. It is not a clinical efficacy, diagnostic accuracy, safety certification, or regulatory-clearance study.

## Research questions

The research questions are frozen as follows:

1. **RQ1 — reconstructability.** Can the plane reconstruct the required inputs, transformations, execution configuration, evidence, safeguards, and human disposition for a bounded clinical AI transaction?
2. **RQ2 — tamper detection.** Can the integrity scheme detect mutation, deletion, reordering, broken references, invalid Merkle proofs, and invalid signatures?
3. **RQ3 — overhead.** What latency and storage overhead does complete capture introduce compared with an identical unrecorded clinical workflow?
4. **RQ4 — reviewer console (system demonstration).** Can the audit console expose evidence, uncertainty, guardrail failures, and human disposition as recorded artifacts? This question is answered with a `SCRIPTED_PROXY` reconstruction and a UI demonstration. It is not a human-subject usability study, and this paper does not claim validated clinical reviewer performance.
5. **RQ5 — replay fidelity.** How much replay fidelity is possible for a deterministic stub versus a hosted nondeterministic model?

Headline ARC is `independently_verified_arc`, computed from reloaded persisted records plus the in-repository verifier module. The metric name is a technical identifier; it does not mean an external third-party audit. `field_presence_arc` is reported separately and must not be treated as the research definition of ARC.

## Benchmark design

Use versioned synthetic FHIR bundles and a small versioned evidence corpus. Run each case through the same declared workflow:

- complete clean transactions;
- missing input, transformation, evidence, tool, guardrail, or human-action events;
- changed model version, prompt version, output, timestamp, reviewer action, or evidence digest;
- deleted and reordered events;
- wrong content references or corpus versions;
- invalid signatures and substituted batch proofs from another transaction;
- deterministic-stub replay and selected hosted-model replay.

The benchmark must retain the ground-truth mutation applied to each case and must distinguish a correctly detected tamper from an ordinary workflow failure.

## Baselines

Compare the complete plane against at least:

1. ordinary application logging with correlated text/JSON records;
2. hash-only logging without an event chain, Merkle batch, or signature;
3. FHIR `Provenance`/`AuditEvent` projection without the internal event model;
4. the complete provenance plane with protected-content references, typed events, chain verification, Merkle proofs, and signatures.

Application JSONL and hash-only JSONL are separately instrumented from the unrecorded clinical workflow. The FHIR projection is built from the source bundle. These are not independently shipped products; the complete plane is scored from the signed audit chain. Recorded and unrecorded paths share the same FHIR assembly and completion stages; the recorded path only emits audit events and proofs afterward so the RQ3 comparator cannot drift from a duplicated pipeline.

The baseline comparison should measure completeness, detection, queryability, overhead, and reviewer-facing field reconstruction. It must not imply that the baselines are clinically unsafe; they answer different audit questions. Reviewer-facing scores in the prototype harness are `SCRIPTED_PROXY` reconstructions on synthetic fixtures. They are not an IRB human usability study.

## Metrics

| Metric | Definition | Initial target or reporting rule |
|---|---|---|
| Audit Reconstruction Completeness (`independently_verified_arc`) | Required provenance fields reconstructed from persisted records after the in-repository verifier succeeds, divided by total required fields | At least 95% on clean benchmark; report missing fields explicitly |
| Field-presence ARC (`field_presence_arc`) | Required provenance fields present on the in-memory transaction object divided by total required fields | Report separately; not a substitute for reload-and-verify ARC |
| Required-event completeness | Required event types present with valid links divided by required event types | 100% for successful transactions |
| Tamper detection rate | Tampered cases correctly flagged divided by all tampered cases | 100% for the defined mutation suite |
| False tamper rate | Clean cases incorrectly flagged divided by all clean cases | 0% on fixtures; report as a rate over at least three independent clean runs, not a single binary result |
| Replay fidelity | Exact, equivalent, or divergent classification under predefined comparison rules | Report by provider and configuration |
| Evidence attribution coverage | Output claims with valid evidence references divided by claims requiring evidence | At least 90% in structured-output benchmark |
| Human-action capture completeness | Review runs with actor, action, time, and final-output digest divided by runs reaching review | 100% |
| Capture overhead | Added latency and storage relative to an identical unrecorded clinical workflow | Report relative allocated overhead `(B_plane - B_base) / B_base` and total allocated multiplier `B_plane / B_base` separately; also report logical serialized bytes excluding SQLite page allocation; do not claim a 15% target unless that baseline is met |
| Verification latency | Time to verify one transaction and one batch proof | Under one second locally for target fixture size |
| Reviewer task success | Correct identification of source, model, evidence, guardrail, and human action | `SCRIPTED_PROXY` only in this paper; not a human-subject usability result |

## Reproducibility package

Before paper submission, publish or archive:

- synthetic FHIR fixtures and evidence corpus version identifiers;
- event schemas and canonicalization rules;
- verifier and benchmark mutation generator;
- configuration manifests, dependency versions, and seeds where applicable;
- baseline implementations and evaluation commands;
- the reproducible `curie-audit-plane evaluate --output-dir <path> --encounters 50 --repetitions 1` command,
  versioned JSON/CSV report artifacts, and the generated vector cohort figure;
- generated tables, figures, and UI screenshots;
- threat model, limitations, data-handling statement, and ethics/IRB statement if human reviewers participate.

## J-BHI evidence gates

The J-BHI route is credible only if the manuscript:

- frames the problem as biomedical and health-informatics provenance for EHR/FHIR workflows;
- includes a healthcare-specific comparison, not only generic observability baselines;
- explains the human review and clinical-data boundary;
- reports synthetic-data generation and access assumptions;
- separates auditability, security, interoperability, and usability from clinical correctness;
- includes reproducible schemas, verifier logic, benchmark cases, and limitations.

If the results are primarily software-engineering or infrastructure evidence, IEEE Access or an engineering/health-informatics conference may be a better fallback than overstating J-BHI fit.

## Current prototype evaluation command

The default run processes 50 synthetic FHIR encounters once using the configured
completer (`CAP_LLM_PROVIDER=stub` or `openai_compatible`). Write stub and live-model
reports to separate `--output-dir` paths. Increase `--encounters` up to 1,000 and repeat
the same cohort with `--repetitions` when estimating latency and storage distributions.
Cohort metrics include mean, median, and normal-approximation 95% confidence intervals.
The in-repository verifier module is invoked after reloading persisted records for every observation. Tamper
detection remains reported from the representative mutation suite because the mutations are
defined against one sealed transaction; this is an explicit limitation rather than a cohort claim.

### Scenario-matrix coverage

Every `curie-audit-plane evaluate` run also executes the 16-arm workflow scenario
matrix. Its protocol, expected qualitative outcomes, artifact-directory rules,
limitations, and measured-result interpretation are defined in
`docs/evaluation/scenario-matrix.md`. Scenario rows establish workflow coverage;
they do not replace the mutation suite for RQ2 or fixed-configuration cohort runs
for RQ3.

## Remaining before J-BHI submission

This draft is positioned as a **single-workflow protocol and system
demonstration**. Remaining gates that cannot be closed in-repo:

- **Gate C:** a second person must run `docs/evaluation/independent-exercise.md`
  and sign `papers/jbhi/GATE_C_ATTESTATION.md`.
- IEEE PDF Checker, DOI, portal article/access selection, reviewer invitation,
  and a tagged clean-clone release proof.
- Recheck J-BHI author instructions immediately before submission.
