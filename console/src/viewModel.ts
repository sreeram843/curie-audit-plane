import eventStages from "../../contracts/event-stages.json";

export type EventRecord = {
  event_id: string;
  transaction_id: string;
  sequence_number: number;
  event_type: string;
  actor_service: string;
  occurred_at: string;
  status: string;
  payload_ref: string | null;
  payload_digest: string | null;
  payload_metadata: Record<string, unknown>;
  previous_event_hash: string;
  event_hash: string;
  schema_version: string;
  hash_status?: string;
};

export type TransactionOverview = {
  transaction_id: string;
  purpose: string;
  subject_ref: string;
  status: string;
  verification_status: string;
  human_action: string;
  started_at: string;
  ended_at: string | null;
  event_count: number;
  missing_event_count: number;
  failed_event_count: number;
};

export const STAGE_ORDER = [
  "transaction.started",
  "input.manifest.created",
  "transformation.applied",
  "context.manifest.created",
  "retrieval.completed",
  "tool.called",
  "tool.completed",
  "model.requested",
  "model.responded",
  "structured_output.validated",
  "guardrail.completed",
  "human.action_recorded",
  "transaction.completed",
  "integrity.proof_committed",
];

export const STATUS_LABELS: Record<string, string> = {
  STARTED: "Started",
  RUNNING: "Running",
  WAITING_FOR_REVIEW: "Waiting for review",
  COMPLETED: "Completed",
  FAILED: "Failed",
  BLOCKED: "Blocked",
  INCOMPLETE: "Incomplete",
  TAMPERED: "Tampered",
  RECORDED: "Recorded",
  VERIFIED: "Verified",
  WARNING: "Warning",
  MISSING: "Missing",
  PASS: "Pass",
  WARN: "Warn",
  BLOCK: "Block",
  ERROR: "Error",
  NOT_RUN: "Not run",
  PENDING: "Pending",
  ACCEPT: "Accept",
  MODIFY: "Modify",
  REJECT: "Reject",
  EXACT_MATCH: "EXACT_MATCH",
  EQUIVALENT: "EQUIVALENT",
  DIVERGENT: "DIVERGENT",
  NOT_REPLAYABLE: "NOT_REPLAYABLE",
};

const STAGES = eventStages as Record<string, string>;

export function statusLabel(value: string): string {
  return STATUS_LABELS[value] ?? value;
}

export function filterEvents(
  events: EventRecord[],
  filters: {
    status?: string;
    eventType?: string;
    stage?: string;
    stages?: string[];
    actor?: string;
    eventIds?: string[];
  },
): EventRecord[] {
  return events.filter((event) => {
    if (filters.status && event.status !== filters.status) return false;
    if (filters.eventType && event.event_type !== filters.eventType) return false;
    if (filters.actor && event.actor_service !== filters.actor) return false;
    if (filters.stage && stageFor(event.event_type) !== filters.stage) return false;
    if (filters.stages && !filters.stages.includes(stageFor(event.event_type))) return false;
    if (filters.eventIds && !filters.eventIds.includes(event.event_id)) return false;
    return true;
  });
}

export function stageFor(eventType: string): string {
  return STAGES[eventType] ?? "transaction";
}

export function sortEvents(
  events: EventRecord[],
  column: keyof EventRecord,
  direction: "asc" | "desc",
): EventRecord[] {
  const copy = [...events];
  copy.sort((left, right) => {
    const a = left[column] ?? "";
    const b = right[column] ?? "";
    if (a < b) return direction === "asc" ? -1 : 1;
    if (a > b) return direction === "asc" ? 1 : -1;
    return 0;
  });
  return copy;
}

export function eventForEvidence(events: EventRecord[], evidenceId: string): EventRecord | undefined {
  return events.find((event) => {
    const meta = JSON.stringify(event.payload_metadata);
    return meta.includes(evidenceId);
  });
}

export const FLOW_STAGES = [
  { id: "fhir_inputs", label: "FHIR inputs" },
  { id: "transformations", label: "Transformations" },
  { id: "context", label: "Context" },
  { id: "retrieval_tools", label: "Retrieval tools" },
  { id: "model", label: "Model" },
  { id: "structured_output", label: "Structured output" },
  { id: "guardrails", label: "Guardrails" },
  { id: "human_action", label: "Human action" },
  { id: "integrity_proof", label: "Integrity proof" },
] as const;

export function chainLabel(_status: string, verification: string): string {
  return verification || "NOT_RUN";
}

export function eventHashStatuses(events: EventRecord[]): Record<string, string> {
  const statuses: Record<string, string> = {};
  for (const event of events) {
    statuses[event.event_id] = event.hash_status ?? "NOT_RUN";
  }
  return statuses;
}

export function consecutiveRuns(events: EventRecord[]): EventRecord[][] {
  const runs: EventRecord[][] = [];
  for (const event of events) {
    const last = runs[runs.length - 1];
    if (last && last[0].event_type === event.event_type) last.push(event);
    else runs.push([event]);
  }
  return runs;
}

export function formatEventTime(iso: string): string {
  const match = /T([0-9:.]+)/.exec(iso);
  return match ? `${match[1].slice(0, 12)}Z` : iso;
}

export function latestGuardrail(events: EventRecord[]): { result: string; message: string } | null {
  const matches = events.filter((event) => event.event_type === "guardrail.completed");
  if (!matches.length) return null;
  const last = matches[matches.length - 1];
  return {
    result: String(last.payload_metadata.result ?? last.status),
    message: String(last.payload_metadata.message ?? ""),
  };
}
