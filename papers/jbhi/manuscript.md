# A Privacy-Preserving Provenance Plane for Reconstructable FHIR-to-LLM Clinical AI Transactions

**Draft for IEEE Journal of Biomedical and Health Informatics (Regular Paper)**
**Official IEEE source:** `papers/jbhi/main.tex` (IEEEtran journal class, same author packaging as the companion Curie FHIR J-BHI manuscript). Compile to `main.pdf` before portal upload.

**Author:** Satya Venkata Ranga Janaki Sriram Mentey (corresponding)
Address: 8601 Anderson Mill Rd, Apt 722, Austin, TX 78729, USA
E-mail: srirammentey@ieee.org · ORCID: [0009-0007-2681-006X](https://orcid.org/0009-0007-2681-006X)

## Abstract

Clinical AI systems that consume electronic health record (EHR) data and emit reviewer-facing summaries create an auditability gap: ordinary application logs rarely preserve the inputs, transformations, model configuration, evidence, safeguards, and human disposition needed to reconstruct a transaction, while storing raw clinical payloads or hidden model reasoning in an immutable log is unsafe. This paper presents Curie Audit Plane, a provenance method for one bounded synthetic FHIR-to-LLM transaction. The plane separates protected clinical content from an append-only audit chain, records typed events with content digests, and verifies hash chaining, Merkle inclusion, and Ed25519 signatures. Structured model output is constrained to rationale, evidence references, uncertainty, assumptions, and missing data; hidden chain-of-thought is rejected. We evaluate reconstructability, tamper detection, replay, and capture overhead on synthetic FHIR fixtures against separately instrumented application-log and hash-only recorders of the same unrecorded workflow, plus a FHIR projection from the source bundle. Headline Audit Reconstruction Completeness is computed from reloaded persisted records after independent verification, not from in-memory field presence alone. The audit console is reported as a system demonstration with scripted field reconstruction (`SCRIPTED_PROXY`); this work is not a human-subject usability study, a clinical-efficacy trial, or a regulatory submission.

**Keywords:** FHIR, clinical AI, provenance, auditability, integrity, health information systems

## I. Introduction

Large language models are being attached to EHR workflows for summarization and review support. Healthcare organizations still need to answer a narrower question: given one completed transaction, can an investigator reconstruct what the model was shown, how it was configured, which evidence and safeguards were applied, and what a human reviewer decided, without placing raw protected health information or hidden reasoning into an immutable store?

This paper treats that question as a biomedical and health-informatics provenance problem, not as generic software logging. The first prototype is deliberately narrow: one synthetic FHIR R4 encounter, one structured clinical-summary task, and a human ACCEPT/MODIFY/REJECT disposition.

The frozen research questions are:

1. Reconstructability of required provenance fields for a bounded FHIR-to-LLM transaction.
2. Detection of mutation, omission, reordering, broken references, and invalid proofs.
3. Latency and storage overhead of complete capture versus ordinary application logging.
4. Console exposure of evidence, uncertainty, guardrail results, and disposition as a system demonstration (`SCRIPTED_PROXY`), not a blinded reviewer study.
5. Replay fidelity for a deterministic stub versus a hosted nondeterministic model.

## II. Related Work

Healthcare provenance and audit have a long FHIR-native literature, including W3C PROV mappings and FHIR `Provenance`/`AuditEvent` resources used to record agents, entities, and access [3]–[5]. Those resources are necessary interoperability projections; they are not, by themselves, an internal event chain with independent cryptographic verification.

Clinical decision-support logging and EHR audit trails typically record who accessed what, not the full AI transaction: input manifests, transformation records, prompt/model identity, retrieved evidence digests, guardrail outcomes, and the human handoff. Model-provider traces and application JSON logs can retain payloads that should not be immutable, or they omit the links required for reconstruction.

This work is closest to tamper-evident logging and hash-chained audit [1], [2], combined with a clinical-data boundary. It does not replace deterministic alert governance, FHIR access control, or the LLM provider. Related comparisons in the evaluation are application JSON logging, hash-only records without signatures, and FHIR-only projection.

## III. Methods

### A. System boundary

Curie Audit Plane observes a synthetic FHIR-to-LLM workflow. Protected payloads (assembled context, model request/response, reviewer-modified text, and free-form comments) are stored in an authorized content store. The immutable audit store holds metadata, opaque references, schemas, and digests. Reviewer comments on the chain are limited to a controlled category; detailed text is protected. Provider exception text is not stored or fingerprinted.

### B. Event model and integrity

A successful transaction emits typed events from input manifestation through human action and an integrity-proof commitment. Events are canonically hashed, chained, batched with a Merkle root, and signed. Verification reports `VERIFIED`, `INCOMPLETE`, `TAMPERED`, or `FAILED`. FHIR R4 `Provenance` and `AuditEvent` resources are documented projections of the internal model, not a claimed Implementation Guide profile.

### C. Structured output and guardrails

Model output must validate as structured rationale. Guardrails record schema validity, evidence-reference coverage, uncertainty presence, a synthetic identifier scan, and policy action. Blocking results require an explicit override policy before ACCEPT.

### D. Evaluation protocol

The reproducible command is `curie-audit-plane evaluate --output-dir <path> --encounters N --repetitions R`. Reports use schema `curie-evaluation.v1.1` and include experiment metadata (git commit, fixture alias and digest, Python version, platform, seed, and command template) without absolute local paths as publication identifiers.

Metrics:

- `field_presence_arc`: in-memory required-field presence.
- `independently_verified_arc`: required-field presence after reloading persisted records, counted only when independent verification succeeds. This is the headline ARC.
- Tamper detection over 19 labeled mutation cases, each with expected ground truth, verifier status, and false-negative/false-positive flags.
- Replay classified as `EXACT_MATCH`, `EQUIVALENT`, or `DIVERGENT`.
- Overhead: isolated stores, warmup, repeated measurements, paired confidence intervals, separate audit-metadata and protected-content bytes, compared with an identical unrecorded clinical workflow (load, transform, context, retrieve, complete, guardrails, JSONL) plus the complete plane.

  - Latency: `(T_plane - T_no_audit_workflow) / T_no_audit_workflow`
  - Storage: `(bytes_plane - bytes_no_audit_workflow) / bytes_no_audit_workflow`

- Ablations: reconstructability after omitting input manifests, transformations, model/prompt metadata, evidence references, cryptographic proofs, or human provenance.
- Access control: allowed and denied HTTP outcomes for reviewer, investigator, admin, output, content, export, missing transaction, and global list scope.

Baselines are separately instrumented recorders of the same unrecorded workflow (application JSONL and hash-only JSONL) or a projection from the source FHIR bundle; they are not independently shipped products. The complete plane is scored from the signed audit chain. Rate metrics use Wilson intervals; latency ratios use paired differences.

### E. Threat model

Adversaries may mutate, delete, or reorder events; substitute proofs or keys; present unsupported findings; or attempt to place PHI in reviewer comments, provider errors, research exports, or LLM endpoint configuration. The prototype assumes synthetic data, local keys, and an approved loopback LLM endpoint. It does not claim protection against compromised signing keys or a malicious protected-content store operator.

### F. Ethics and data

The evaluation uses synthetic FHIR fixtures and optional external Synthea bundles [6] that are not committed to this repository. Discovery is limited to roots listed in `fixtures/synthea/approved-manifest.json`. Synthea generator version, population seed, module set, and CLI are **NOT_PINNED** / not measured. No real patient records or human participants were analyzed. Therefore no IRB protocol was required for this prototype. If a later study recruits reviewers, that work needs separate ethics review and consent. The authors report no specific funding for this prototype and declare no competing interests.

### G. AI-use disclosure

Portions of software and documentation were drafted with assistance from coding agents. All evaluation metrics are produced by the versioned Python harness. Authors remain responsible for claims, code, and the decision to submit.

## IV. Results

Engineering checks at the time of this draft: 143 Python tests, 94.59% statement coverage, Ruff clean, and 15 console tests with a production build. These are software-quality results, not clinical performance.

On the synthetic fixture benchmark, independently verified ARC meets the 95% clean-transaction target, all 19 labeled tamper cases are detected, and false tamper rate over three clean runs is 0. The complete plane reconstructs more required fields and detects the standard model-event mutation that application logs and FHIR projections do not detect. Hash-only logging detects digest mismatch without providing chain or signature guarantees.

Hosted-model same-prompt replay is at best `EQUIVALENT` and is often `DIVERGENT`. Prompt-substitution replay is `DIVERGENT` by construction. The 16-arm scenario matrix exercises ACCEPT/MODIFY/REJECT, natural WARN/BLOCK, provider failure, Synthea slices, and access audit; it is workflow coverage, not a population sample. The two Synthea slice arms are unpinned demonstrations and are excluded from measured tables. Ablation rows show reconstructability dropping when manifests, transformations, model metadata, evidence, proofs, or human provenance are omitted. Access-control cases report allowed and denied outcomes for reviewer, investigator, admin, output, content, export, missing-record, and global-scope probes.

Overhead on the stub campaign is 14.78 ms versus 9.15 ms for the identical unrecorded workflow (paired latency ratio 0.615, 95% interval [0.594, 0.637], n=3 after one warmup). Storage ratio is 6.31. Clean-transaction verification is 1.07 ms. Treat large latency or storage ratios as real negative results; this draft does not claim that audit capture is under 15% of an already-complete clinical application.

## V. Discussion and Limitations

This is a single-workflow protocol demonstration. The default cohort rewrites one fixture; it is not 50 independent patients and does not support population-style inference. Immutable audit metadata stores opaque subject and resource tokens; the protected identity map is required for authorized reconstruction. Research export applies schema-aware pseudonymization and must not be confused with a de-identification certification. FHIR projections are mapping rules for R4 `Provenance` and `AuditEvent`, not Implementation Guide profile validation. Rate confidence intervals are Wilson binomial intervals; latency uses paired differences. A DOI and IEEE PDF Checker pass remain before portal upload. J-BHI page limits, fees, and supplementary rules must be rechecked on the journal site.

The paper does not claim clinical efficacy, diagnostic accuracy, safety certification, or validated human usability.

## VI. Conclusion

A FHIR-to-LLM provenance plane can reconstruct and independently verify a bounded synthetic clinical-AI transaction, detect a defined mutation suite, and keep hidden reasoning and free-form reviewer text out of the immutable chain. Remaining work is experimental scale and IEEE Author Portal packaging.

## References

[1] B. Schneier and J. Kelsey, “Cryptographic Support for Secure Logs on Untrusted Machines,” in *Proc. 7th USENIX Security Symp.*, San Antonio, TX, USA, 1998, pp. 53–62. [Online]. Available: https://www.usenix.org/conference/7th-usenix-security-symposium/cryptographic-support-secure-logs-untrusted-machines

[2] S. A. Crosby and D. S. Wallach, “Efficient Data Structures for Tamper-Evident Logging,” in *Proc. 18th USENIX Security Symp.*, Montreal, QC, Canada, 2009, pp. 317–334. [Online]. Available: https://www.usenix.org/legacy/event/sec09/tech/full_papers/crosby.pdf

[3] HL7 International, “Provenance,” FHIR Release 4, 2019. [Online]. Available: http://hl7.org/fhir/R4/provenance.html

[4] HL7 International, “AuditEvent,” FHIR Release 4, 2019. [Online]. Available: http://hl7.org/fhir/R4/auditevent.html

[5] World Wide Web Consortium, “PROV-DM: The PROV Data Model,” W3C Recommendation, Apr. 30, 2013. [Online]. Available: https://www.w3.org/TR/prov-dm/

[6] J. Walonoski *et al.*, “Synthea: An approach, method, and software mechanism for generating synthetic patients and the synthetic electronic health care record,” *J. Amer. Med. Inform. Assoc.*, vol. 25, no. 3, pp. 230–238, Mar. 2018, doi: 10.1093/jamia/ocx079.

[7] IEEE Engineering in Medicine and Biology Society, “IEEE Journal of Biomedical and Health Informatics.” [Online]. Available: https://www.embs.org/jbhi/

## Supplementary Material

Versioned synthetic fixtures, event schemas, verifier, mutation labels, evaluation command, and JSON/CSV report artifacts. Do not include `.env`, signing keys, protected payloads, or raw Synthea dumps in the public archive.

## Data and Code Availability

Source is released under the MIT license (`LICENSE`, `CITATION.cff`). Evaluation reports are regenerated with `curie-audit-plane evaluate`. A stable DOI is not assigned in this draft. IEEE template source is `papers/jbhi/main.tex`.
