import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { api, downloadJson } from "./api";

vi.mock("./api", () => ({
  api: vi.fn(),
  downloadJson: vi.fn(),
}));

vi.mock("echarts-for-react", () => ({
  default: ({
    onEvents,
  }: {
    onEvents?: {
      click?: (params: {
        name?: string;
        dataType?: string;
        data?: { source?: string; target?: string; event_ids?: string[] };
      }) => void;
    };
  }) => (
    <div>
      <button type="button" onClick={() => onEvents?.click?.({ name: "retrieval_tools", dataType: "node", data: { event_ids: ["evt-1"] } })}>
        Sankey node
      </button>
      <button
        type="button"
        onClick={() =>
          onEvents?.click?.({
            dataType: "edge",
            data: { source: "retrieval_tools", target: "model", event_ids: ["evt-1", "evt-2"] },
          })
        }
      >
        Sankey edge
      </button>
    </div>
  ),
}));

const mockedApi = vi.mocked(api);
const mockedDownload = vi.mocked(downloadJson);

const event = {
  event_id: "evt-1",
  transaction_id: "tx-1",
  sequence_number: 0,
  event_type: "retrieval.completed",
  actor_service: "curie-audit-plane",
  occurred_at: "2026-08-27T17:00:00Z",
  status: "RECORDED",
  payload_ref: "sha256:abc",
  payload_digest: "abc",
  payload_metadata: { chunk_ids: ["htn-bp-target.v1"] },
  previous_event_hash: "00",
  event_hash: "aa",
  schema_version: "1.0.0",
  hash_status: "VERIFIED",
};

const modelEvent = {
  ...event,
  event_id: "evt-2",
  sequence_number: 1,
  event_type: "model.requested",
  payload_metadata: { model_id: "curie-stub-summary" },
  previous_event_hash: "aa",
  event_hash: "bb",
};

const unrelatedEvent = {
  ...event,
  event_id: "evt-3",
  sequence_number: 2,
  event_type: "guardrail.completed",
  payload_metadata: { result: "PASS" },
  previous_event_hash: "bb",
  event_hash: "cc",
  hash_status: "VERIFIED",
};

const detail = {
  transaction: {
    transaction_id: "tx-1",
    purpose: "synthetic-encounter-summary",
    subject_ref: "Patient/TEST-00001",
    status: "WAITING_FOR_REVIEW",
    human_action: "PENDING",
    verification_status: "INCOMPLETE",
    started_at: "2026-08-27T17:00:00Z",
    ended_at: null,
  },
  overview: {
    transaction_id: "tx-1",
    purpose: "synthetic-encounter-summary",
    subject_ref: "Patient/TEST-00001",
    status: "WAITING_FOR_REVIEW",
    verification_status: "INCOMPLETE",
    human_action: "PENDING",
    started_at: "2026-08-27T17:00:00Z",
    ended_at: null,
    event_count: 1,
    missing_event_count: 1,
    failed_event_count: 0,
  },
  verification: {
    status: "INCOMPLETE",
    scope: ["chain"],
    chain_ok: true,
    merkle_ok: true,
    signature_ok: true,
    key_id: "test-key",
    verified_at: "2026-08-27T17:00:00Z",
    missing_events: ["human.action_recorded"],
    hash_failures: [],
    reason: "required events missing",
  },
  output: {
    summary: "Office visit.",
    findings: [{ text: "BP high", evidence_refs: ["htn-bp-target.v1"] }],
    evidence_references: ["htn-bp-target.v1"],
    uncertainty: "Limited.",
    assumptions: [],
    missing_data: [],
    follow_up_questions: [],
  },
};

function renderApp() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

describe("audit console", () => {
  beforeEach(() => {
    mockedApi.mockReset();
    mockedDownload.mockReset();
    mockedApi.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/transactions" && !init?.method) {
        return [{ transaction_id: "tx-1", purpose: "synthetic-encounter-summary", subject_ref: "Patient/TEST-00001", status: "WAITING_FOR_REVIEW" }];
      }
      if (path === "/transactions/run") return detail;
      if (path === "/transactions/tx-1") return detail;
      if (path === "/transactions/tx-1/events") {
        return {
          events: [
            { ...event, hash_status: "VERIFIED" },
            { ...modelEvent, hash_status: "TAMPERED" },
            unrelatedEvent,
          ],
          hash_statuses: { "evt-1": "VERIFIED", "evt-2": "TAMPERED", "evt-3": "VERIFIED" },
        };
      }
      if (path === "/transactions/tx-1/output") return { output: detail.output };
      if (path === "/transactions/tx-1/sankey") {
        return {
          metric: "artifact_count",
          caption: "Recorded artifact flow (edge width = artifact count). Width does not imply causal influence.",
          nodes: [
            { id: "retrieval_tools", label: "retrieval tools", artifact_count: 1, event_ids: ["evt-1"] },
            { id: "model", label: "model", artifact_count: 1, event_ids: ["evt-2"] },
            { id: "guardrails", label: "guardrails", artifact_count: 1, event_ids: ["evt-3"] },
          ],
          edges: [
            {
              source: "retrieval_tools",
              target: "model",
              value: 1,
              metric: "artifact_count",
              event_ids: ["evt-1", "evt-2"],
            },
          ],
          tabular_fallback: [{ stage: "retrieval_tools", artifact_count: 1, event_ids: ["evt-1"] }],
          tabular_fallback_edges: [
            { source: "retrieval_tools", target: "model", artifact_count: 2, event_ids: ["evt-1", "evt-2"] },
          ],
        };
      }
      if (path === "/transactions/tx-1/verify") {
        return { ...detail.verification, status: "VERIFIED", reason: "", missing_events: [] };
      }
      if (path === "/transactions/tx-1/replay") {
        return {
          result: "EXACT_MATCH",
          original_digest: "aa",
          replay_digest: "aa",
          reasons: [],
          original_output: detail.output,
          modified_output: null,
          replay_output: detail.output,
          original_event_id: "evt-1",
          modified_event_id: null,
        };
      }
      if (path === "/transactions/tx-1/review") {
        return detail;
      }
      if (path.endsWith("/export") || path.endsWith("/research-export")) {
        return { export_type: path.includes("research") ? "research" : "clinical_authorized" };
      }
      throw new Error(`unmocked ${path}`);
    });
  });

  it("selects a transaction, reviews, verifies, and replays", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    expect(await screen.findByText("synthetic-encounter-summary")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "ACCEPT" }));
    await waitFor(() => {
      const reviews = mockedApi.mock.calls.filter(([path]) => path === "/transactions/tx-1/review");
      expect(reviews).toHaveLength(1);
      const body = JSON.parse(String(reviews[0][1]?.body ?? "{}"));
      expect(body.action).toBe("ACCEPT");
      expect(body.actor).toBeUndefined();
    });
    fireEvent.click(screen.getByRole("button", { name: "Verify integrity" }));
    await waitFor(() => expect(mockedApi).toHaveBeenCalledWith("/transactions/tx-1/verify", expect.objectContaining({ method: "POST" })));
    fireEvent.click(screen.getByRole("button", { name: "Replay" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Original output" })).toBeTruthy());
    expect(screen.getByRole("heading", { name: "Original output" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Modified output" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Replay output" })).toBeTruthy();
    expect(screen.getByText("No human modification recorded")).toBeTruthy();
  });

  it("shows review progress and prevents duplicate submissions", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    await screen.findByText("synthetic-encounter-summary");

    let resolveReview: (value: typeof detail) => void = () => undefined;
    const pendingReview = new Promise<typeof detail>((resolve) => {
      resolveReview = resolve;
    });
    const previous = mockedApi.getMockImplementation();
    mockedApi.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/transactions/tx-1/review") return pendingReview;
      if (previous) return previous(path, init);
      throw new Error(`unmocked pending-state request ${path}`);
    });

    const accept = screen.getByRole("button", { name: "ACCEPT" });
    fireEvent.click(accept);
    fireEvent.click(accept);

    expect(await screen.findByText("Accepting…")).toBeTruthy();
    expect((accept as HTMLButtonElement).disabled).toBe(true);
    expect(mockedApi.mock.calls.filter(([path]) => path === "/transactions/tx-1/review")).toHaveLength(1);

    resolveReview(detail);
    await waitFor(() => expect((screen.getByRole("button", { name: "ACCEPT" }) as HTMLButtonElement).disabled).toBe(false));
  });

  it("shows verification progress and prevents duplicate integrity requests", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    await screen.findByText("synthetic-encounter-summary");

    let resolveVerification: (value: typeof detail.verification) => void = () => undefined;
    const pendingVerification = new Promise<typeof detail.verification>((resolve) => {
      resolveVerification = resolve;
    });
    const previous = mockedApi.getMockImplementation();
    mockedApi.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/transactions/tx-1/verify") return pendingVerification;
      if (previous) return previous(path, init);
      throw new Error(`unmocked pending-state request ${path}`);
    });

    const verify = screen.getByRole("button", { name: "Verify integrity" });
    fireEvent.click(verify);
    fireEvent.click(verify);

    expect(await screen.findByText("Verifying…")).toBeTruthy();
    expect((verify as HTMLButtonElement).disabled).toBe(true);
    expect(mockedApi.mock.calls.filter(([path]) => path === "/transactions/tx-1/verify")).toHaveLength(1);

    resolveVerification(detail.verification);
    await waitFor(() =>
      expect((screen.getByRole("button", { name: "Verify integrity" }) as HTMLButtonElement).disabled).toBe(false),
    );
  });

  it("filters by status, toggles JSON, downloads, and navigates evidence", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    await screen.findByText("Event table");
    fireEvent.change(screen.getByLabelText(/Status/), { target: { value: "RECORDED" } });
    fireEvent.change(screen.getByLabelText(/Actor/), { target: { value: "curie-audit-plane" } });
    expect(screen.getByRole("button", { name: "retrieval.completed" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sankey node" }));
    fireEvent.click(screen.getByRole("button", { name: "Sankey edge" }));
    fireEvent.click(screen.getByRole("button", { name: "Download research export" }));
    fireEvent.click(screen.getByRole("button", { name: "Download clinical export" }));
    fireEvent.click(screen.getByRole("tab", { name: "Raw" }));
    fireEvent.click(screen.getByRole("tab", { name: "Formatted" }));
    fireEvent.click(screen.getByRole("button", { name: "Download event JSON" }));
    expect(mockedDownload).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "htn-bp-target.v1" }));
    await waitFor(() => expect(screen.getAllByText("required events missing").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Incomplete").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Verified").length).toBeGreaterThan(0);
    expect(screen.queryByText("OPEN")).toBeNull();
    expect(screen.queryByText("INTACT")).toBeNull();
    expect(screen.queryByText("BROKEN")).toBeNull();
    expect(screen.queryByText("Flagged")).toBeNull();
  });

  it("uses timeline buttons with keyboard activation", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    const timeline = (await screen.findAllByRole("button", { name: /retrieval.completed/ }))[0];
    timeline.focus();
    fireEvent.keyDown(timeline, { key: "Enter" });
    fireEvent.keyDown(timeline, { key: " " });
    expect(timeline).toBeTruthy();
  });

  it("shows run progress and locks selected-transaction actions", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    await screen.findByText("synthetic-encounter-summary");

    let resolveRun: (value: typeof detail) => void = () => undefined;
    const pendingRun = new Promise<typeof detail>((resolve) => {
      resolveRun = resolve;
    });
    const previous = mockedApi.getMockImplementation();
    mockedApi.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/transactions/run") return pendingRun;
      if (previous) return previous(path, init);
      throw new Error(`unmocked pending-state request ${path}`);
    });

    const run = screen.getByRole("button", { name: "Run synthetic transaction" });
    fireEvent.click(run);
    fireEvent.click(run);
    expect(await screen.findByText("Running…")).toBeTruthy();
    expect(await screen.findByText("Running transaction…")).toBeTruthy();
    expect((run as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "ACCEPT" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Verify integrity" }) as HTMLButtonElement).disabled).toBe(true);
    expect(mockedApi.mock.calls.filter(([path]) => path === "/transactions/run")).toHaveLength(1);

    resolveRun(detail);
    await waitFor(() => expect((screen.getByRole("button", { name: "Run synthetic transaction" }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.getByText("Transaction complete")).toBeTruthy();
  });

  it("shows an accessible error and re-enables buttons after failure", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    await screen.findByText("synthetic-encounter-summary");

    const previous = mockedApi.getMockImplementation();
    mockedApi.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path === "/transactions/tx-1/verify") throw new Error("integrity check failed");
      if (previous) return previous(path, init);
      throw new Error(`unmocked pending-state request ${path}`);
    });

    fireEvent.click(screen.getByRole("button", { name: "Verify integrity" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Integrity verification failed/);
    expect(alert.textContent).toMatch(/integrity check failed/);
    expect((screen.getByRole("button", { name: "Verify integrity" }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "ACCEPT" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("filters Sankey clicks to the exact linked event IDs", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    await screen.findByText("Event table");
    fireEvent.click(await screen.findByRole("button", { name: "Sankey edge" }));
    expect(screen.getByRole("button", { name: "retrieval.completed" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "model.requested" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "guardrail.completed" })).toBeNull();
    expect(screen.getAllByText("Tampered").length).toBeGreaterThan(0);
  });

  it("shows timeline status text and a keyboard Sankey reset", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    const timeline = await screen.findAllByRole("button", { name: /retrieval.completed/ });
    expect(timeline[0].textContent).toMatch(/Recorded/);
    fireEvent.click(await screen.findByRole("button", { name: "retrieval_tools → model" }));
    expect(screen.queryByRole("button", { name: "guardrail.completed" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    fireEvent.click(screen.getByRole("button", { name: "Pan right" }));
    fireEvent.click(screen.getByRole("button", { name: "Reset view" }));
    expect(screen.getByRole("button", { name: "guardrail.completed" })).toBeTruthy();
  });

  it("navigates the Sankey chart with the keyboard", async () => {
    renderApp();
    fireEvent.click(await screen.findByRole("button", { name: /Patient\/TEST-00001/ }));
    const chart = await screen.findByRole("group", { name: "Sankey recorded artifact flow" });
    chart.focus();
    fireEvent.keyDown(chart, { key: "ArrowRight" });
    expect(screen.queryByRole("button", { name: "guardrail.completed" })).toBeNull();
    fireEvent.keyDown(chart, { key: "ArrowDown" });
    fireEvent.keyDown(chart, { key: "Escape" });
    expect(screen.getByRole("button", { name: "guardrail.completed" })).toBeTruthy();
  });
});
