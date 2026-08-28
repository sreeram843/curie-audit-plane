# Curie Audit Plane Agent Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repository’s required agent workflows, safety boundaries, and skill routing explicit for future implementation sessions.

**Architecture:** Keep project-specific rules in `AGENTS.md` and `.cursor/rules/curie-audit-plane.mdc`; keep the larger skill matrix in `docs/skills-and-workflows.md` so the always-loaded guidance stays short.

**Tech Stack:** Markdown; Cursor project rules; existing IronBee DevTools verification policy; repository documentation.

**Spec:** `docs/PRD.md`

## Global Constraints

- Use synthetic FHIR data for the first prototype.
- Keep raw clinical payloads outside the immutable audit store.
- Do not capture hidden chain-of-thought.
- Preserve the first integration order: `curie-fhir`, then `curie-prediction-pipeline`, then `curie-gateway`.
- Follow the existing IronBee DevTools rule for browser and runtime verification.

---

### Task 1: Project-level agent contract

**Files:**
- Create: `AGENTS.md`
- Create: `.cursor/rules/curie-audit-plane.mdc`

- [x] Define the required documents an agent reads before implementation.
- [x] Define scope, data-handling, explanation, secret-management, and integration guardrails.
- [x] Preserve the existing browser verification rule and explicitly allow docs-only verification to remain non-runtime.

### Task 2: Skill routing reference

**Files:**
- Create: `docs/skills-and-workflows.md`
- Modify: `README.md`

- [x] Map core and supporting skills to concrete Curie tasks.
- [x] Define routing for domain changes, implementation, security boundaries, UI, research, and completion checks.
- [x] Add the routing guide to the README.

### Task 3: Guidance verification

**Files:**
- Read: `AGENTS.md`, `.cursor/rules/curie-audit-plane.mdc`, `docs/skills-and-workflows.md`, and `README.md`

- [x] Check terminology against `CONTEXT.md` and `docs/PRD.md`.
- [x] Check that guidance does not authorize PHI, hidden reasoning, production EHR access, or unreviewed scope expansion.
- [x] Check local documentation links and repository status.

