# Evaluation report schema

Current schema: `curie-evaluation.v1.1`.

`v1.1` is a backward-compatible extension of `curie-evaluation.v1`. Readers of `v1`
may ignore unknown keys. Publishers should emit `v1.1`.

## Added or redefined in v1.1

- `experiment`: portable run metadata (git commit, dirty-tree flag, fixture alias and digest,
  recorded provider and model, prompt version, decoding parameters, endpoint class, seed,
  Python version, platform, command template, timestamp, Synthea license/source, and
  Synthea pin status). Absolute local
  paths are not used as the publication fixture identifier. `synthea_version` is
  `NOT_PINNED` unless `generator_version` is recorded.
- `metrics` names `field_presence_arc` and `independently_verified_arc`.
  `audit_reconstruction_completeness` remains and equals reload-and-verify ARC
  after the in-repository verifier succeeds. The metric name does not imply an
  external auditor.
- `overhead` records warmup, repetition count (`n=30`), paired confidence
  intervals, allocated file sizes (including SQLite pages), logical serialized
  bytes (UTF-8 octet length of event JSON, transaction-row payloads, and
  protected-content files), relative overhead
  `(B_plane - B_base) / B_base`, and total multiplier `B_plane / B_base`.
- `baselines[].implementation` identifies the recording method.
- `baselines[].independence` is `unrecorded_workflow`, `source_bundle`, or `audit_chain`.
  Application JSONL and hash-only JSONL are separately instrumented from the
  unrecorded workflow; they are not independently shipped products.
- `cases[]` mutation labels: `mutation_type`, `expected_detected`,
  `false_positive`, `false_negative`, `verifier_status`.
- `scenarios` remains the 16-arm workflow matrix from `v1`.
- `ablations[]` reconstructability after omitting manifests, transformations, model metadata,
  evidence, proofs, or human provenance.
- `access_control.cases[]` allowed and denied HTTP outcomes for reviewer, investigator, admin,
  output, content, export, missing-record, and global-scope probes.

## Compatibility

CSV `row_type` values are `metric`, `case`, `scenario`, `ablation`, and `access`.
New metric names appear as additional `metric` rows. Scenario matrix results are
published inside `evaluation-results/` (and the live companion directory), not as a
separate ignored artifact.
