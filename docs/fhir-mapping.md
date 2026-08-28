# FHIR mapping rules (R4)

Internal audit events remain the lossless source. FHIR resources below are interoperable projections, not a replacement for the event chain.

## Provenance

Generated from a completed transaction:

| FHIR R4 field | Source |
|---|---|
| `resourceType` | `Provenance` |
| `target` | Protected-content reference of `structured_output.validated` |
| `recorded` | Transaction end time |
| `activity.text` | Transaction purpose |
| `agent[author].who.display` | `curie-audit-plane` |
| `agent[reviewer].who.display` | Human-action actor |
| `entity` | Source `Patient/` / `Encounter/` identifiers from the input manifest, plus prompt/model manifest identity |

## AuditEvent

One `AuditEvent` is projected per internal event:

| FHIR R4 field | Source |
|---|---|
| `type` | REST audit-event-type coding |
| `subtype` | FHIR R4 `CodeableConcept`: `{ "coding": [{ "system", "code", "display" }] }` where `code` is the internal dotted event type |
| `recorded` | Event `occurred_at` |
| `agent.who.display` | `actor_service` |
| `entity.detail` | `transaction_id`, `event_hash`, `sequence_number` |

Provenance source entities use `resource_type`/`resource_id` pairs from the input manifest, not ID-prefix guessing. The model manifest is projected as an identifier (`https://curie.local/model-manifest`) plus digest metadata.

## Limitations

- Projections are documented FHIR R4 mapping rules, not a conformance claim against a
  specific Implementation Guide or StructureDefinition profile. The paper is limited
  to these mapping rules.
- Cryptographic chain, Merkle proof, and signature material stay in the internal event model.
- Hashes and identifiers in these resources are sensitive metadata, not anonymizers.
