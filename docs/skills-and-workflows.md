# Skills and workflows

This document maps the reusable agent skills to Curie Audit Plane work. It is a project routing guide, not a copy of the global skill packages.

## Core skills

| Skill | Use when | Project output or gate |
|---|---|---|
| `domain-modeling` | Adding or changing terms, entities, boundaries, or `CONTEXT.md` | Glossary and relationship language stay canonical. |
| `writing-plans` | A change spans multiple files, services, or evaluation steps | A checked implementation plan with file ownership and verification steps. |
| `lean-build` | Building a new product slice or integration with overbuilding risk | One complete narrow path, explicit non-goals, and a clear stop condition. |
| `tdd-workflow` | Adding code, APIs, schemas, verifiers, or UI behavior | RED → GREEN → coverage evidence; tests cover unit, integration, and critical UI paths. |
| `security-review` | Handling FHIR content, user input, secrets, APIs, authentication, authorization, storage, tools, or providers | Threats, controls, and verification for sensitive-data boundaries. |
| `frontend-design` | Designing or implementing the audit console | Intentional information hierarchy, readable statuses, accessible interaction, and non-generic visual language. |
| `research` | Gathering standards, prior art, venue rules, or technical evidence | Primary-source findings captured in a repository Markdown document. |
| `verify-and-stop` | Validating a completed slice or documentation task | Smallest sufficient proof set, with pass/fail/unavailable stated precisely. |

## Supporting skills

| Skill | Use when | Constraint |
|---|---|---|
| `doc-coauthoring` | Revising the PRD, architecture, research plan, or other structured documents | Keep the reader, decision, and acceptance signal explicit; prune stale duplication. |
| `prototype` | Exploring a UI state model or visualization before production implementation | Throwaway exploration only; promote behavior into the PRD before building it. |
| `requesting-code-review` | Completing a major implementation slice or before merge | Review against both the PRD and repository standards. |
| `code-review` | Reviewing a branch or diff against specification and standards | Report concrete findings with file locations and severity. |
| `webapp-testing` | Only when project rules permit its browser tooling | This repository currently requires IronBee DevTools for browser work; follow `.cursor/rules/ironbee-devtools-use.mdc` instead. |

## Workflow routing

```text
New request
   |
   +-- terminology/boundary change ----> domain-modeling
   |
   +-- multi-file implementation ------> writing-plans -> lean-build -> tdd-workflow
   |
   +-- FHIR/API/secret/data boundary ---> security-review (before implementation)
   |
   +-- audit console/visualization ------> frontend-design -> tdd-workflow
   |
   +-- paper/standards/venue evidence ---> research -> research-plan
   |
   +-- completion check -----------------> verify-and-stop
```

## Shared project gates

Every implementation slice must preserve these gates:

1. The first workflow remains one synthetic FHIR-to-LLM transaction.
2. Raw clinical payloads remain outside the immutable audit store.
3. Hidden chain-of-thought is not captured; structured rationale is used instead.
4. Required events, statuses, links, hashes, and verification scope are machine-readable.
5. UI views include tables/JSON and accessible text alternatives in addition to charts.
6. Research metrics include Audit Reconstruction Completeness and tamper detection.
7. Claims about auditability are not presented as claims of clinical efficacy or regulatory clearance.

