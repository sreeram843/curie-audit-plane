# Evaluation report schema

Current schema: `curie-evaluation.v1.1`.

`v1.1` is a backward-compatible extension of `curie-evaluation.v1`. Readers of `v1`
may ignore unknown keys. Publishers should emit `v1.1`.

## Added or redefined in v1.1

- `experiment`: portable run metadata (git commit, dirty-tree flag, fixture alias and digest,
  recorded provider and model, prompt version, decoding parameters, endpoint class, seed,
  Python version, platform, command template, timestamp, Synthea license/source). Absolute local
  paths are not used as the publication fixture identifier.
- `metrics` names `field_presence_arc` and `independently_verified_arc`.
  `audit_reconstruction_completeness` remains and equals independently verified ARC.
- `overhead` records warmup, repetition count, paired confidence intervals, separate
  audit-metadata and protected-content storage, and explicit formulas against an identical
  no-audit clinical workflow.
- `baselines[].implementation` identifies the independent recording method.
- `cases[]` mutation labels: `mutation_type`, `expected_detected`,
  `false_positive`, `false_negative`, `verifier_status`.
- `scenarios` remains the 16-arm workflow matrix from `v1`.
- `ablations[]` reconstructability after omitting manifests, transformations, model metadata,
  evidence, proofs, or human provenance.
- `access_control.cases[]` allowed and denied HTTP outcomes for reviewer, investigator, admin,
  output, content, export, missing-record, and global-scope probes.

## Compatibility

CSV `row_type` values `metric`, `case`, and `scenario` are unchanged. New metric
names appear as additional `metric` rows.
