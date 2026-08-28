import { describe, expect, it } from "vitest";
import eventStages from "../../contracts/event-stages.json";
import {
  chainLabel,
  consecutiveRuns,
  eventHashStatuses,
  filterEvents,
  sortEvents,
  stageFor,
  statusLabel,
  type EventRecord,
} from "./viewModel";

const sample: EventRecord[] = [
  {
    event_id: "1",
    transaction_id: "tx",
    sequence_number: 1,
    event_type: "guardrail.completed",
    actor_service: "curie-audit-plane",
    occurred_at: "2026-08-27T17:00:01Z",
    status: "WARNING",
    payload_ref: null,
    payload_digest: null,
    payload_metadata: { result: "WARN" },
    previous_event_hash: "aa",
    event_hash: "bb",
    schema_version: "1.0.0",
  },
  {
    event_id: "0",
    transaction_id: "tx",
    sequence_number: 0,
    event_type: "input.manifest.created",
    actor_service: "curie-audit-plane",
    occurred_at: "2026-08-27T17:00:00Z",
    status: "RECORDED",
    payload_ref: "sha256:abc",
    payload_digest: "abc",
    payload_metadata: {},
    previous_event_hash: "00",
    event_hash: "aa",
    schema_version: "1.0.0",
  },
];

describe("audit console view model", () => {
  it("exposes text labels for PRD statuses", () => {
    expect(statusLabel("TAMPERED")).toBe("Tampered");
    expect(statusLabel("WAITING_FOR_REVIEW")).toBe("Waiting for review");
    expect(statusLabel("BLOCK")).toBe("Block");
    expect(statusLabel("PASS")).toBe("Pass");
    expect(statusLabel("WARN")).toBe("Warn");
    expect(statusLabel("FAILED")).toBe("Failed");
    expect(statusLabel("MISSING")).toBe("Missing");
    expect(statusLabel("INCOMPLETE")).toBe("Incomplete");
    expect(statusLabel("VERIFIED")).toBe("Verified");
    expect(statusLabel("ERROR")).toBe("Error");
    expect(statusLabel("ACCEPT")).toBe("Accept");
    expect(statusLabel("MODIFY")).toBe("Modify");
    expect(statusLabel("REJECT")).toBe("Reject");
  });

  it("maps every contracted event type to its canonical stage", () => {
    for (const [eventType, stage] of Object.entries(eventStages)) {
      expect(stageFor(eventType)).toBe(stage);
    }
  });

  it("filters by status, stage, and actor", () => {
    expect(filterEvents(sample, { status: "WARNING" })).toHaveLength(1);
    expect(filterEvents(sample, { stage: "fhir_inputs" })[0].event_type).toBe("input.manifest.created");
    expect(filterEvents(sample, { actor: "curie-audit-plane" })).toHaveLength(2);
    expect(filterEvents(sample, { eventIds: ["1"] })).toHaveLength(1);
    expect(filterEvents(sample, { eventIds: ["1"] })[0].event_id).toBe("1");
    expect(stageFor("integrity.proof_committed")).toBe("integrity_proof");
    expect(statusLabel("FAILED")).toBe("Failed");
    expect(statusLabel("MISSING")).toBe("Missing");
    expect(statusLabel("VERIFIED")).toBe("Verified");
  });

  it("sorts by sequence", () => {
    const sorted = sortEvents(sample, "sequence_number", "asc");
    expect(sorted.map((event) => event.sequence_number)).toEqual([0, 1]);
  });

  it("groups consecutive identical event types and labels the chain", () => {
    const access = { ...sample[0], event_type: "ui.access_recorded", event_id: "a" };
    const runs = consecutiveRuns([access, { ...access, event_id: "b" }, { ...access, event_id: "c" }, sample[1]]);
    expect(runs[0]).toHaveLength(3);
    expect(runs[1][0].event_type).toBe("input.manifest.created");
    expect(chainLabel("RUNNING", "INCOMPLETE")).toBe("INCOMPLETE");
    expect(chainLabel("COMPLETED", "VERIFIED")).toBe("VERIFIED");
    expect(chainLabel("COMPLETED", "TAMPERED")).toBe("TAMPERED");
    expect(chainLabel("RUNNING", "")).toBe("NOT_RUN");
    const missing = eventHashStatuses(sample);
    expect(missing["0"]).toBe("NOT_RUN");
    expect(missing["1"]).toBe("NOT_RUN");
    const tampered = eventHashStatuses([
      { ...sample[0], hash_status: "TAMPERED", previous_event_hash: sample[1].event_hash },
      sample[1],
    ]);
    expect(tampered["1"]).toBe("TAMPERED");
    const verified = eventHashStatuses([{ ...sample[1], hash_status: "VERIFIED" }]);
    expect(verified["0"]).toBe("VERIFIED");
  });
});
