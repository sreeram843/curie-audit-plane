# Curie Audit Plane Context

This glossary defines the domain language for Curie Audit Plane / Clinical AI Flight Recorder. It intentionally excludes implementation details.

## Terms

### Curie Audit Plane
The named system boundary for the Curie family’s verifiable provenance capability. It receives audit events from clinical AI workflows and preserves the relationship between clinical inputs, transformations, model execution, evidence, safeguards, human actions, and integrity proofs.

### Clinical AI transaction
One bounded request-response workflow in which a defined set of clinical data is assembled, an AI system produces a structured output, safeguards run, and a human reviewer records an action.

### Audit plane / flight recorder
The system of record for verifiable operational provenance around a Clinical AI transaction. It stores manifests, evidence references, system events, safeguard results, human actions, and cryptographic integrity proofs; it does not store hidden chain-of-thought.

### Input manifest
The machine-readable inventory of source resources and derived inputs presented to the AI, including stable identifiers, versions or timestamps, transformations, and content digests.

### Transformation
A documented, reproducible operation that changes or selects source data before model execution, such as filtering, normalization, de-identification, summarization, or context-window ordering.

### Model manifest
The identity and configuration record for the model execution, including model family/version, serving endpoint, prompt/template version, decoding parameters, tool policy, and execution timestamp.

### Evidence item
A retrievable, addressable piece of patient context or external clinical knowledge that supports or constrains the structured output. Each evidence item has provenance and a digest.

### Structured rationale
A concise, schema-constrained explanation of the output: findings, evidence references, assumptions, uncertainty, contraindications, and decision factors. It is an audit artifact, not a transcript of hidden model reasoning.

### Guardrail result
The recorded outcome of a safety or policy check applied to inputs, retrieved evidence, model output, or the proposed action.

### Human action
The reviewer’s explicit disposition of the AI output: ACCEPT, MODIFY, or REJECT, with optional comment and timestamp.

### Transaction status
The lifecycle and trust state of a Clinical AI transaction, such as RUNNING, WAITING_FOR_REVIEW, COMPLETED, FAILED, INCOMPLETE, or TAMPERED.

### Verification status
The result of checking a requested integrity scope, including the event chain, Merkle proof, and signature.

