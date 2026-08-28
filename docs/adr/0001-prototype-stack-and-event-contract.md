# ADR 0001: Prototype stack and event contract

**Status:** Accepted  
**Date:** 2026-08-27

## Context

The repository was documentation-only. The first implementation must observe one synthetic FHIR-to-LLM transaction without replacing `curie-fhir`, without storing raw clinical payloads in the immutable log, and without capturing hidden chain-of-thought.

## Decision

1. Implement a Python 3.11 modular monolith using FastAPI, Pydantic v2, SQLite, and the `cryptography` Ed25519 API, matching the `curie-fhir` runtime family.
2. Persist PRD dotted event type strings (`transaction.started`). Architecture `TRANSACTION_STARTED` names are documentation aliases only.
3. Keep protected clinical payloads in a content-addressed file store keyed by SHA-256. The audit store records metadata, opaque `sha256:` references, schemas, and digests.
4. Integrate with `curie-fhir` conceptually: FHIR R4 resources, synthetic fixtures, provenance envelopes, and human review. Do not import or replace the `curie-fhir` pipeline. `curie-prediction-pipeline` and `curie-gateway` remain later adapters.
5. Use a deterministic LLM stub for tests and the default path. An optional OpenAI-compatible adapter targets local LM Studio. Hosted cloud providers remain deferred.
6. Serve the audit console as a React/TypeScript Vite app against a typed view-model API.

## Consequences

- Local `pytest` can verify capture, integrity, and reconstruction without network services.
- Event JSON remains stable if storage or UI technology changes.
- A later FastAPI-to-curie-fhir HTTP adapter can emit the same event types without rewriting the verifier.
