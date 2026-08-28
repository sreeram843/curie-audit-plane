import { useEffect, useMemo, useState, type KeyboardEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { api, downloadJson } from "./api";
import {
  FLOW_STAGES,
  chainLabel,
  consecutiveRuns,
  eventForEvidence,
  eventHashStatuses,
  filterEvents,
  formatEventTime,
  latestGuardrail,
  sortEvents,
  stageFor,
  statusLabel,
  type EventRecord,
  type TransactionOverview,
} from "./viewModel";

type TxRow = {
  transaction_id: string;
  purpose: string;
  subject_ref: string;
  status: string;
};

type Detail = {
  transaction: {
    transaction_id: string;
    purpose: string;
    subject_ref: string;
    status: string;
    human_action: string;
    verification_status: string;
    started_at: string;
    ended_at: string | null;
  };
  overview: TransactionOverview;
  verification: {
    status: string;
    scope: string[];
    chain_ok: boolean;
    merkle_ok: boolean;
    signature_ok: boolean;
    key_id: string;
    verified_at: string;
    missing_events: string[];
    hash_failures: string[];
    reason: string;
    content_ok?: boolean;
  };
  output: {
    summary: string;
    findings: { text: string; evidence_refs: string[] }[];
    evidence_references: string[];
    uncertainty: string;
    assumptions: string[];
    missing_data: string[];
    follow_up_questions: string[];
  } | null;
};

type Sankey = {
  metric: string;
  caption: string;
  nodes: { id: string; label: string; artifact_count: number; event_ids?: string[] }[];
  edges: { source: string; target: string; value: number; event_ids?: string[] }[];
  tabular_fallback: { stage: string; artifact_count: number; event_ids?: string[] }[];
  tabular_fallback_edges?: { source: string; target: string; artifact_count: number; event_ids?: string[] }[];
};

type Replay = {
  result: string;
  original_digest: string;
  replay_digest: string;
  reasons: string[];
  original_output?: Detail["output"];
  modified_output?: Detail["output"] | null;
  replay_output?: Detail["output"];
  original_event_id?: string | null;
  modified_event_id?: string | null;
};

type OperationStatus = {
  label: string;
  state: "working" | "success" | "error";
  detail?: string;
};

function errorDetail(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed. Try again.";
}

function OperationFeedback({
  operation,
  announce = false,
}: {
  operation: OperationStatus | null;
  announce?: boolean;
}) {
  if (!operation) return null;
  const working = operation.state === "working";
  const failed = operation.state === "error";
  const role = announce ? (failed ? "alert" : "status") : undefined;
  return (
    <div
      className={`operation-feedback operation-${operation.state}`}
      role={role}
      aria-live={announce ? "polite" : undefined}
    >
      <span className={working ? "operation-spinner is-spinning" : "operation-icon"} aria-hidden="true">
        {working ? "◌" : failed ? "!" : "✓"}
      </span>
      <span>
        {working ? `${operation.label}…` : failed ? `${operation.label} failed` : `${operation.label} complete`}
        {operation.detail ? <span className="operation-detail"> · {operation.detail}</span> : null}
      </span>
    </div>
  );
}

function toneForStatus(status: string): string {
  if (status === "RUNNING") return "var(--live)";
  if (status === "FAILED" || status === "TAMPERED" || status === "BLOCK" || status === "REJECT" || status === "ERROR") {
    return "var(--bad)";
  }
  if (status === "COMPLETED" || status === "VERIFIED" || status === "PASS" || status === "ACCEPT") return "var(--ok)";
  return "var(--warn)";
}

function toneForLifecycle(status: string, failed: number): string {
  if (failed > 0) return "var(--bad)";
  return toneForStatus(status);
}

function chipKindForStatus(status: string): "ok" | "warn" | "bad" | "live" {
  const tone = toneForStatus(status);
  if (tone === "var(--ok)") return "ok";
  if (tone === "var(--bad)") return "bad";
  if (tone === "var(--live)") return "live";
  return "warn";
}

function eventDot(event: EventRecord): string {
  if (event.status === "FAILED" || event.status === "TAMPERED" || event.status === "BLOCK") return "var(--bad)";
  if (stageFor(event.event_type) === "human_action") return "var(--live)";
  return "var(--ok)";
}

function Chip({
  children,
  kind = "stage",
  status,
}: {
  children: ReactNode;
  kind?: "stage" | "ok" | "warn" | "bad" | "live" | "mute" | "status";
  status?: string;
}) {
  return (
    <span className={`chip chip-${kind}`} data-chip="" data-status={status}>
      {children}
    </span>
  );
}

export function App() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [eventFilter, setEventFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [jsonMode, setJsonMode] = useState<"formatted" | "raw">("formatted");
  const [activeEventId, setActiveEventId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<keyof EventRecord>("sequence_number");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [comment, setComment] = useState("");
  const [linkedEventIds, setLinkedEventIds] = useState<string[] | null>(null);
  const [sankeyZoom, setSankeyZoom] = useState(1);
  const [sankeyPan, setSankeyPan] = useState({ x: 0, y: 0 });
  const [sankeyFocus, setSankeyFocus] = useState(-1);
  const [actorFilter, setActorFilter] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState(false);
  const [operation, setOperation] = useState<OperationStatus | null>(null);

  const list = useQuery({
    queryKey: ["transactions"],
    queryFn: () => api<TxRow[]>("/transactions"),
  });

  const run = useMutation({
    mutationFn: () => api<Detail>("/transactions/run", { method: "POST", body: JSON.stringify({}) }),
    onSuccess: (data) => {
      const id = data.transaction.transaction_id;
      setSelectedId(id);
      setOperation({ label: "Transaction", state: "success" });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["transaction", id] });
      queryClient.invalidateQueries({ queryKey: ["events", id] });
      queryClient.invalidateQueries({ queryKey: ["sankey", id] });
      queryClient.invalidateQueries({ queryKey: ["output", id] });
    },
    onError: (error) => setOperation({ label: "Transaction", state: "error", detail: errorDetail(error) }),
  });

  const detail = useQuery({
    queryKey: ["transaction", selectedId],
    enabled: Boolean(selectedId),
    queryFn: () => api<Detail>(`/transactions/${selectedId}`),
  });

  const eventsQuery = useQuery({
    queryKey: ["events", selectedId],
    enabled: Boolean(selectedId),
    queryFn: () => api<{ events: EventRecord[] }>(`/transactions/${selectedId}/events`),
  });

  const outputQuery = useQuery({
    queryKey: ["output", selectedId],
    enabled: Boolean(selectedId),
    retry: false,
    queryFn: () => api<{ output: Detail["output"] }>(`/transactions/${selectedId}/output`),
  });

  const sankeyQuery = useQuery({
    queryKey: ["sankey", selectedId],
    enabled: Boolean(selectedId) && (eventsQuery.data?.events.length ?? 0) > 0,
    queryFn: () => api<Sankey>(`/transactions/${selectedId}/sankey`),
  });

  const verify = useMutation({
    mutationFn: () => api<Detail["verification"]>(`/transactions/${selectedId}/verify`, { method: "POST" }),
    onSuccess: () => {
      setOperation({ label: "Integrity verification", state: "success" });
      queryClient.invalidateQueries({ queryKey: ["transaction", selectedId] });
    },
    onError: (error) => setOperation({ label: "Integrity verification", state: "error", detail: errorDetail(error) }),
  });

  const replay = useMutation({
    mutationFn: () => api<Replay>(`/transactions/${selectedId}/replay`, { method: "POST" }),
    onSuccess: () => setOperation({ label: "Replay", state: "success" }),
    onError: (error) => setOperation({ label: "Replay", state: "error", detail: errorDetail(error) }),
  });

  const exportClinical = useMutation({
    mutationFn: () => api<unknown>(`/transactions/${selectedId}/export`),
    onSuccess: (payload) => {
      downloadJson(`transaction-${selectedId}-export.json`, payload);
      setOperation({ label: "Clinical export", state: "success" });
    },
    onError: (error) => setOperation({ label: "Clinical export", state: "error", detail: errorDetail(error) }),
  });

  const exportResearch = useMutation({
    mutationFn: () => api<unknown>(`/transactions/${selectedId}/research-export`),
    onSuccess: (payload) => {
      downloadJson(`transaction-${selectedId}-research.json`, payload);
      setOperation({ label: "Research export", state: "success" });
    },
    onError: (error) => setOperation({ label: "Research export", state: "error", detail: errorDetail(error) }),
  });

  const review = useMutation({
    mutationFn: (action: "ACCEPT" | "MODIFY" | "REJECT") =>
      api<Detail>(`/transactions/${selectedId}/review`, {
        method: "POST",
        body: JSON.stringify({
          action,
          comment,
          modified_output:
            action === "MODIFY"
              ? {
                  summary: comment || "Clinician-adjusted summary.",
                  findings: [{ text: "Reviewer-modified finding", evidence_refs: ["obs-bp-TEST-00001"] }],
                  evidence_references: ["obs-bp-TEST-00001"],
                  uncertainty: "Human modification applied.",
                  assumptions: [],
                  missing_data: [],
                  follow_up_questions: [],
                }
              : undefined,
        }),
      }),
    onSuccess: () => {
      setOperation({ label: "Review action", state: "success" });
      queryClient.invalidateQueries({ queryKey: ["transaction", selectedId] });
      queryClient.invalidateQueries({ queryKey: ["events", selectedId] });
      queryClient.invalidateQueries({ queryKey: ["sankey", selectedId] });
      queryClient.invalidateQueries({ queryKey: ["output", selectedId] });
    },
    onError: (error) => setOperation({ label: "Review action", state: "error", detail: errorDetail(error) }),
  });

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const events = eventsQuery.data?.events ?? [];
  const filtered = sortEvents(
    filterEvents(events, {
      eventType: eventFilter || undefined,
      status: statusFilter || undefined,
      stage: stageFilter || undefined,
      actor: actorFilter || undefined,
      eventIds: linkedEventIds ?? undefined,
    }),
    sortKey,
    sortDir,
  );
  const active = filtered.find((event) => event.event_id === activeEventId) ?? filtered[0];
  const overview = detail.data?.overview;
  const verification = verify.data ?? detail.data?.verification;
  const output = outputQuery.data?.output ?? null;
  const sankey = sankeyQuery.data;
  const chain = overview ? chainLabel(overview.status, overview.verification_status) : "NOT_RUN";
  const hashStatuses = eventHashStatuses(events);
  const guard = latestGuardrail(events);
  const counts = FLOW_STAGES.map((stage) => ({
    ...stage,
    count: events.filter((event) => stageFor(event.event_type) === stage.id).length,
  }));
  const maxCount = Math.max(1, ...counts.map((stage) => stage.count));
  const missingStages = FLOW_STAGES.filter((stage) => counts.find((item) => item.id === stage.id)?.count === 0);
  const runs = consecutiveRuns(filtered);

  const option = useMemo(() => {
    if (!sankey) return {};
    return {
      backgroundColor: "transparent",
      textStyle: { color: "#8b96a4", fontFamily: "IBM Plex Sans" },
      tooltip: { trigger: "item" },
      series: [
        {
          type: "sankey",
          data: sankey.nodes.map((node) => ({ name: node.id, event_ids: node.event_ids })),
          links: sankey.edges.map((edge) => ({
            source: edge.source,
            target: edge.target,
            value: edge.value,
            event_ids: edge.event_ids,
          })),
          lineStyle: { color: "gradient", curveness: 0.4 },
          label: { color: "#cfd8e2" },
        },
      ],
    };
  }, [sankey]);

  function toggleSort(column: keyof EventRecord) {
    if (sortKey === column) setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
    else {
      setSortKey(column);
      setSortDir("asc");
    }
  }

  function selectTransaction(id: string) {
    setSelectedId(id);
    setStageFilter("");
    setLinkedEventIds(null);
    setSankeyZoom(1);
    setSankeyPan({ x: 0, y: 0 });
    setSankeyFocus(-1);
    setActorFilter("");
    setActiveEventId(null);
    setExpanded({});
    setComment("");
    setOperation(null);
  }

  function beginOperation(label: string) {
    setOperation({ label, state: "working" });
  }

  function submitReview(action: "ACCEPT" | "MODIFY" | "REJECT") {
    beginOperation(`${action[0]}${action.slice(1).toLowerCase()} review`);
    review.mutate(action);
  }

  function selectStage(id: string) {
    setLinkedEventIds(null);
    setStageFilter((current) => (current === id ? "" : id));
    setActiveEventId(null);
  }

  function resetView() {
    setStageFilter("");
    setLinkedEventIds(null);
    setSankeyZoom(1);
    setSankeyPan({ x: 0, y: 0 });
    setSankeyFocus(-1);
  }

  function selectLinkedRecords(ids: string[] | undefined) {
    setStageFilter("");
    const linked = ids?.length ? ids : null;
    setLinkedEventIds(linked);
    if (linked) setActiveEventId(linked[0]);
  }

  function selectEdge(source: string, target: string, eventIds?: string[]) {
    if (eventIds?.length) {
      selectLinkedRecords(eventIds);
      return;
    }
    const edge = sankey?.edges.find((item) => item.source === source && item.target === target);
    selectLinkedRecords(edge?.event_ids);
  }

  function panSankey(dx: number, dy: number) {
    setSankeyPan((current) => ({ x: current.x + dx, y: current.y + dy }));
  }

  function handleSankeyKey(event: KeyboardEvent<HTMLDivElement>) {
    const targets = [
      ...(sankey?.nodes ?? []).map((node) => ({ event_ids: node.event_ids })),
      ...(sankey?.edges ?? []).map((edge) => ({ event_ids: edge.event_ids })),
    ];
    if (event.key === "Escape") {
      event.preventDefault();
      resetView();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      panSankey(0, 24);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      panSankey(0, -24);
      return;
    }
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      if (!targets.length) return;
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const next = (sankeyFocus + delta + targets.length) % targets.length;
      setSankeyFocus(next);
      selectLinkedRecords(targets[next]?.event_ids);
    }
  }

  function focusEvidence(ref: string) {
    const match = eventForEvidence(events, ref);
    if (match) {
      setActiveEventId(match.event_id);
      setStageFilter(stageFor(match.event_type));
      setLinkedEventIds(null);
    }
  }

  function copyJson() {
    if (!active) return;
    void navigator.clipboard.writeText(JSON.stringify(active, null, 2));
    setCopied(true);
  }

  const dims = active
    ? [
        ["event_type", active.event_type],
        ["actor_service", active.actor_service],
        ["stage", stageFor(active.event_type)],
        ["occurred_at", active.occurred_at],
        ["payload_ref", active.payload_ref ?? "—"],
        ...Object.entries(active.payload_metadata).map(([key, value]) => [
          key,
          typeof value === "object" ? JSON.stringify(value) : String(value),
        ]),
      ]
    : [];

  const guardValue = guard?.result ?? "NOT_RUN";
  const guardTone = toneForStatus(guardValue);
  const actionBusy =
    run.isPending ||
    verify.isPending ||
    replay.isPending ||
    exportClinical.isPending ||
    exportResearch.isPending ||
    review.isPending;

  return (
    <div className="app">
      <aside className="rail">
        <div className="rail-brand">
          <div className="kicker">Clinical AI flight recorder</div>
          <div className="brand-row">
            <div className="live-dot" aria-hidden="true" />
            <h1>Curie Audit Plane</h1>
          </div>
          <button
            type="button"
            className="btn-run"
            data-action="run-synthetic"
            aria-label="Run synthetic transaction"
            onClick={() => {
              beginOperation("Running transaction");
              run.mutate();
            }}
            disabled={run.isPending || actionBusy}
          >
            <span className="plus" aria-hidden="true">
              +
            </span>
            <span>{run.isPending ? "Running…" : "Run synthetic transaction"}</span>
          </button>
          <OperationFeedback operation={operation} announce />
        </div>
        <div className="rail-head">
          <div className="kicker" style={{ letterSpacing: "0.16em" }}>
            Transactions
          </div>
          <div className="count">{list.data?.length ?? 0}</div>
        </div>
        <ul className="tx-list">
          {(list.data ?? []).map((row) => {
            const selected = row.transaction_id === selectedId;
            const failed = row.status === "FAILED" || row.status === "TAMPERED";
            return (
              <li key={row.transaction_id} data-tx="">
                <button
                  type="button"
                  className="tx-row"
                  aria-selected={selected}
                  onClick={() => selectTransaction(row.transaction_id)}
                >
                  <div className="tx-row-top">
                    <span
                      className="tx-dot"
                      data-pulse={row.status === "RUNNING"}
                      style={{ background: toneForLifecycle(row.status, failed ? 1 : 0) }}
                    />
                    <span className="tx-id">{row.transaction_id.slice(0, 8)}</span>
                  </div>
                  <div className="tx-subject">{row.subject_ref}</div>
                  <div className="tx-state">
                    <span>{statusLabel(row.status)}</span>
                    {failed ? <Chip kind="bad">1 FAILED</Chip> : null}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
        <div className="rail-foot">
          <span>schema 1.0.0</span>
          <span>producer 0.1.0</span>
        </div>
      </aside>
      <main className="workspace">
        {!overview ? (
          <p className="empty">Run or select a synthetic FHIR-to-LLM transaction to inspect provenance.</p>
        ) : (
          <>
            <header className="workspace-header">
              <div>
                <h2 className="page-title">{overview.purpose}</h2>
                <p className="page-meta">
                  {overview.subject_ref} · {overview.transaction_id}
                </p>
              </div>
              <div className="chain-block" aria-label="Hash chain ticker">
                <div className="kicker" style={{ letterSpacing: "0.16em" }}>
                  Hash chain
                </div>
                <div className="chain-row">
                  <span>{active ? `${active.previous_event_hash.slice(0, 16)}…` : "—"}</span>
                  <span style={{ color: "#3c4653" }}>→</span>
                  <span style={{ color: "#cfd8e2" }}>{active ? `${active.event_hash.slice(0, 16)}…` : "—"}</span>
                  <Chip kind={chipKindForStatus(chain)}>{statusLabel(chain)}</Chip>
                </div>
              </div>
            </header>
            <section className="tiles" aria-label="Transaction overview">
              <article className="tile" data-tile="" style={{ borderTopColor: toneForLifecycle(overview.status, overview.failed_event_count) }}>
                <div className="tile-label">Transaction</div>
                <div className="tile-value-row">
                  <div className="tile-value" style={{ color: toneForLifecycle(overview.status, overview.failed_event_count) }}>
                    {statusLabel(overview.status)}
                  </div>
                  {overview.status === "RUNNING" ? <Chip kind="live">LIVE</Chip> : null}
                </div>
                <div className="tile-note">
                  {overview.started_at.slice(11, 19)}Z → {overview.ended_at ? overview.ended_at.slice(11, 19) + "Z" : "in progress"}
                </div>
              </article>
              <article className="tile" data-tile="" style={{ borderTopColor: toneForStatus(overview.verification_status) }}>
                <div className="tile-label">Verification</div>
                <div className="tile-value-row">
                  <div className="tile-value" style={{ color: toneForStatus(overview.verification_status) }}>
                    {statusLabel(overview.verification_status)}
                  </div>
                  <Chip kind={chipKindForStatus(chain)}>{statusLabel(chain)}</Chip>
                </div>
                <div className="tile-note">{verification?.reason || `Verification ${statusLabel(chain)} · ${overview.event_count} links`}</div>
              </article>
              <article className="tile" data-tile="" style={{ borderTopColor: guardTone }}>
                <div className="tile-label">Guardrails</div>
                <div className="tile-value-row">
                  <div className="tile-value" style={{ color: guardTone }}>
                    {statusLabel(guardValue)}
                  </div>
                </div>
                <div className="tile-note">{guard?.message || "No guardrail event recorded yet"}</div>
              </article>
              <article className="tile" data-tile="" style={{ borderTopColor: missingStages.length ? "var(--warn)" : "var(--ok)" }}>
                <div className="tile-label">Evidence</div>
                <div className="tile-value-row">
                  <div className="tile-value" style={{ color: missingStages.length ? "var(--warn)" : "var(--ok)" }}>
                    {FLOW_STAGES.length - missingStages.length} / {FLOW_STAGES.length}
                  </div>
                  <Chip kind="warn">STAGES</Chip>
                </div>
                <div className="tile-note">
                  {missingStages.length ? `${missingStages.length} stages without artifacts` : "Every pipeline stage has artifacts"}
                </div>
              </article>
              <article className="tile" data-tile="" style={{ borderTopColor: toneForStatus(overview.human_action) }}>
                <div className="tile-label">Human action</div>
                <div className="tile-value-row">
                  <div className="tile-value" style={{ color: toneForStatus(overview.human_action) }}>
                    {statusLabel(overview.human_action)}
                  </div>
                </div>
                <div className="tile-note">
                  {overview.human_action === "PENDING"
                    ? "No accept / modify / reject on record"
                    : "Recorded human disposition"}
                </div>
              </article>
              <article className="tile" data-tile="" style={{ borderTopColor: overview.failed_event_count ? "var(--bad)" : overview.missing_event_count ? "var(--warn)" : "var(--ok)" }}>
                <div className="tile-label">Missing / failed</div>
                <div className="tile-value-row">
                  <div
                    className="tile-value"
                    style={{
                      color: overview.failed_event_count ? "var(--bad)" : overview.missing_event_count ? "var(--warn)" : "var(--ok)",
                    }}
                  >
                    {overview.missing_event_count} / {overview.failed_event_count}
                  </div>
                </div>
                <div className="tile-note">
                  {overview.failed_event_count ? "Failed events are listed in the timeline" : "Gaps are expected while the run is open"}
                </div>
              </article>
            </section>
            <section className="section">
              <div className="section-head">
                <div className="kicker" style={{ letterSpacing: "0.16em" }}>
                  Recorded artifact flow
                </div>
                <div className="hint">Artifact counts per stage. Click a stage or edge to filter the timeline.</div>
                <div className="flow-view-controls">
                  <button type="button" className="ghost" onClick={() => setSankeyZoom((value) => Math.min(2, value + 0.25))}>
                    Zoom in
                  </button>
                  <button type="button" className="ghost" onClick={() => setSankeyZoom((value) => Math.max(0.75, value - 0.25))}>
                    Zoom out
                  </button>
                  <button type="button" className="ghost" onClick={() => panSankey(-40, 0)}>
                    Pan left
                  </button>
                  <button type="button" className="ghost" onClick={() => panSankey(40, 0)}>
                    Pan right
                  </button>
                  <button type="button" className="ghost" onClick={resetView}>
                    Reset view
                  </button>
                </div>
              </div>
              <div className="flow-grid">
                {counts.map((stage) => {
                  const activeStage = stageFilter === stage.id;
                  const empty = stage.count === 0;
                  const height = 12 + Math.round(46 * (stage.count / maxCount));
                  return (
                    <button
                      key={stage.id}
                      type="button"
                      className="stage-bar"
                      data-stage=""
                      aria-pressed={activeStage}
                      onClick={() => selectStage(stage.id)}
                    >
                      <div
                        className="stage-fill"
                        style={{
                          height,
                          background: empty ? "transparent" : activeStage ? "rgba(106,168,255,.34)" : "rgba(88,214,138,.16)",
                          border: `1px solid ${empty ? "#242b34" : activeStage ? "#6aa8ff" : "rgba(88,214,138,.45)"}`,
                        }}
                      />
                      <div className="stage-rail" style={{ background: empty ? "#242b34" : activeStage ? "#6aa8ff" : "rgba(88,214,138,.55)" }} />
                      <div className="stage-count" style={{ color: empty ? "#3f4854" : activeStage ? "#9cc5ff" : "#e6ebf0" }}>
                        {stage.count}
                      </div>
                      <div className="stage-label" style={{ color: empty ? "#4d5866" : activeStage ? "#cfd8e2" : "#8b96a4" }}>
                        {stage.label}
                      </div>
                    </button>
                  );
                })}
              </div>
              <div className="flow-meta">
                <span>Width does not imply causal influence.</span>
                <span className="spacer">
                  Guardrail {statusLabel(guardValue)} · Verification {statusLabel(verification?.status ?? "NOT_RUN")}
                </span>
                <span>gaps {missingStages.length}</span>
              </div>
              <details
                className="sankey-details"
                onKeyDown={(event) => {
                  if (event.key === "Escape") resetView();
                }}
              >
                <summary>Sankey and tabular fallback (artifact count)</summary>
                <p className="hint">{sankey?.caption}</p>
                {sankey ? (
                  <div
                    className="sankey-viewport"
                    role="group"
                    aria-label="Sankey recorded artifact flow"
                    tabIndex={0}
                    onKeyDown={handleSankeyKey}
                  >
                  <div
                    className="sankey-zoom"
                    style={{
                      transform: `translate(${sankeyPan.x}px, ${sankeyPan.y}px) scale(${sankeyZoom})`,
                      transformOrigin: "top left",
                    }}
                  >
                  <ReactECharts
                    option={option}
                    style={{ height: 220 }}
                    onEvents={{
                      click: (params: {
                        dataType?: string;
                        name?: string;
                        data?: { source?: string; target?: string; event_ids?: string[] };
                      }) => {
                        if (params.dataType === "edge") {
                          selectEdge(params.data?.source ?? "", params.data?.target ?? "", params.data?.event_ids);
                        } else if (params.data?.event_ids?.length) {
                          selectLinkedRecords(params.data.event_ids);
                        } else if (params.name) {
                          const node = sankey.nodes.find((item) => item.id === params.name);
                          if (node?.event_ids?.length) selectLinkedRecords(node.event_ids);
                          else selectStage(params.name);
                        }
                      },
                    }}
                  />
                  </div>
                  </div>
                ) : null}
                <table>
                  <caption>Tabular fallback for the Sankey (artifact count)</caption>
                  <thead>
                    <tr>
                      <th>Stage</th>
                      <th>Artifact count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sankey?.tabular_fallback ?? []).map((row) => (
                      <tr key={row.stage}>
                        <td>
                          <button
                            type="button"
                            className="table-event"
                            onClick={() =>
                              row.event_ids?.length ? selectLinkedRecords(row.event_ids) : selectStage(row.stage)
                            }
                          >
                            {row.stage}
                          </button>
                        </td>
                        <td>{row.artifact_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <table>
                  <caption>Tabular fallback for Sankey edges (handoff records)</caption>
                  <thead>
                    <tr>
                      <th>Edge</th>
                      <th>Artifact count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sankey?.tabular_fallback_edges ?? sankey?.edges ?? []).map((edge) => (
                      <tr key={`${edge.source}-${edge.target}`}>
                        <td>
                          <button
                            type="button"
                            className="table-event"
                            onClick={() => selectEdge(edge.source, edge.target, edge.event_ids)}
                            onKeyDown={(event) => {
                              if (event.key === "Escape") resetView();
                            }}
                          >
                            {edge.source} → {edge.target}
                          </button>
                        </td>
                        <td>{"artifact_count" in edge ? edge.artifact_count : edge.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </section>
            <section className="section">
              <div className="section-head">
                <div className="kicker" style={{ letterSpacing: "0.16em" }}>
                  Event timeline
                </div>
                <div className="hint">
                  {stageFilter ? `Filtered to ${stageFilter.replaceAll("_", " ")} · ` : ""}
                  {linkedEventIds ? `Filtered to ${linkedEventIds.length} linked records · ` : ""}
                  {events.length} events · repeated runs collapsed
                </div>
              </div>
              <ol className="timeline">
                {runs.map((run) => {
                  if (run.length >= 3) {
                    const key = `${run[0].event_type}-${run[0].sequence_number}`;
                    const open = Boolean(expanded[key]);
                    return (
                      <li key={key}>
                        <button
                          type="button"
                          className="group-item"
                          data-group=""
                          aria-expanded={open}
                          onClick={() => setExpanded((current) => ({ ...current, [key]: !current[key] }))}
                        >
                          <div className="seq">
                            {run[0].sequence_number}–{run[run.length - 1].sequence_number}
                          </div>
                          <div className="dot-wrap">
                            <span className="event-dot" style={{ background: "#3f4854" }} />
                          </div>
                          <div className="event-main">
                            <div className="event-line">
                              <span className="event-type" style={{ color: "#9aa6b4" }}>
                                {run[0].event_type}
                              </span>
                              <Chip kind="mute">×{run.length}</Chip>
                              <Chip>{stageFor(run[0].event_type).replaceAll("_", " ")}</Chip>
                            </div>
                            <div className="event-sub">
                              {run.length} identical events · {open ? "collapse" : "expand"}
                            </div>
                          </div>
                          <div className="event-time">{formatEventTime(run[0].occurred_at)} →</div>
                        </button>
                        {open
                          ? run.map((event) => (
                              <button
                                key={event.event_id}
                                type="button"
                                className="timeline-item child"
                                data-event=""
                                aria-current={event.event_id === active?.event_id}
                                onClick={() => setActiveEventId(event.event_id)}
                              >
                                <div className="seq">{event.sequence_number}</div>
                                <div className="dot-wrap">
                                  <span className="event-dot" style={{ background: eventDot(event) }} />
                                </div>
                                <div className="event-main">
                                  <div className="event-line">
                                    <span className="event-type">{event.event_type}</span>
                                    <Chip kind="status" status={event.status}>
                                      {statusLabel(event.status)}
                                    </Chip>
                                    <Chip kind="status" status={hashStatuses[event.event_id] ?? "NOT_RUN"}>
                                      {statusLabel(hashStatuses[event.event_id] ?? "NOT_RUN")}
                                    </Chip>
                                    <Chip>{stageFor(event.event_type).replaceAll("_", " ")}</Chip>
                                  </div>
                                  <div className="event-sub">
                                    {event.payload_ref ?? "no payload ref"} · {event.actor_service}
                                  </div>
                                </div>
                                <div className="event-time">{formatEventTime(event.occurred_at)}</div>
                              </button>
                            ))
                          : null}
                      </li>
                    );
                  }
                  return run.map((event) => (
                    <li key={event.event_id}>
                      <button
                        type="button"
                        className="timeline-item"
                        data-event=""
                        aria-current={event.event_id === active?.event_id}
                        onClick={() => {
                          setActiveEventId(event.event_id);
                          setStageFilter(stageFor(event.event_type));
                          setLinkedEventIds(null);
                        }}
                      >
                        <div className="seq">{event.sequence_number}</div>
                        <div className="dot-wrap">
                          <span className="event-dot" style={{ background: eventDot(event) }} />
                        </div>
                        <div className="event-main">
                          <div className="event-line">
                            <span className="event-type">{event.event_type}</span>
                            <Chip kind="status" status={event.status}>
                              {statusLabel(event.status)}
                            </Chip>
                            <Chip kind="status" status={hashStatuses[event.event_id] ?? "NOT_RUN"}>
                              {statusLabel(hashStatuses[event.event_id] ?? "NOT_RUN")}
                            </Chip>
                            <Chip>{stageFor(event.event_type).replaceAll("_", " ")}</Chip>
                          </div>
                          <div className="event-sub">
                            {event.payload_ref ?? "no payload ref"} · {event.actor_service}
                          </div>
                        </div>
                        <div className="event-time">{formatEventTime(event.occurred_at)}</div>
                      </button>
                    </li>
                  ));
                })}
              </ol>
              {missingStages.length ? (
                <div className="missing-block">
                  <div className="kicker" style={{ letterSpacing: "0.14em" }}>
                    Not recorded
                  </div>
                  <div className="missing-chips">
                    {missingStages.map((stage) => (
                      <div key={stage.id} className="missing-chip">
                        {stage.label}
                      </div>
                    ))}
                  </div>
                  <div className="tile-note">
                    These stages have no artifacts in this transaction. For an open run this is expected; for a completed run it
                    blocks verification.
                  </div>
                </div>
              ) : null}
            </section>
            <section className="section">
              <div className="section-head">
                <h2 className="kicker" style={{ letterSpacing: "0.16em" }}>
                  Event table
                </h2>
              </div>
              <div className="filters">
                <label>
                  Type{" "}
                  <select value={eventFilter} onChange={(event) => setEventFilter(event.target.value)}>
                    <option value="">All types</option>
                    {[...new Set(events.map((item) => item.event_type))].map((type) => (
                      <option key={type}>{type}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Status{" "}
                  <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                    <option value="">All statuses</option>
                    {[...new Set(events.map((item) => item.status))].map((status) => (
                      <option key={status} value={status}>
                        {statusLabel(status)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Stage{" "}
                  <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)}>
                    <option value="">All stages</option>
                    {[...new Set(events.map((item) => stageFor(item.event_type)))].map((stage) => (
                      <option key={stage}>{stage}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Actor{" "}
                  <select value={actorFilter} onChange={(event) => setActorFilter(event.target.value)}>
                    <option value="">All actors</option>
                    {[...new Set(events.map((item) => item.actor_service))].map((actor) => (
                      <option key={actor}>{actor}</option>
                    ))}
                  </select>
                </label>
              </div>
              <table>
                <thead>
                  <tr>
                    {(["sequence_number", "occurred_at", "event_type", "actor_service", "status"] as const).map((column) => (
                      <th key={column}>
                        <button type="button" onClick={() => toggleSort(column)}>
                          {column}
                        </button>
                      </th>
                    ))}
                    <th>payload ref</th>
                    <th>hash verification</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((event) => (
                    <tr key={event.event_id}>
                      <td>{event.sequence_number}</td>
                      <td>{event.occurred_at}</td>
                      <td>
                        <button type="button" className="table-event" onClick={() => setActiveEventId(event.event_id)}>
                          {event.event_type}
                        </button>
                      </td>
                      <td>{event.actor_service}</td>
                      <td>
                        <Chip kind="status" status={event.status}>
                          {statusLabel(event.status)}
                        </Chip>
                      </td>
                      <td className="mono">{event.payload_ref ?? "—"}</td>
                      <td>
                        <Chip kind="status" status={hashStatuses[event.event_id] ?? "NOT_RUN"}>
                          {statusLabel(hashStatuses[event.event_id] ?? "NOT_RUN")}
                        </Chip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          </>
        )}
      </main>
      <aside className="inspector" data-inspector="">
        <div className="inspector-head">
          <div className="inspector-head-row">
            <div className="kicker" style={{ letterSpacing: "0.16em" }}>
              Event inspector
            </div>
            <div className="seg" role="tablist" aria-label="JSON mode">
              <button type="button" role="tab" aria-selected={jsonMode === "formatted"} onClick={() => setJsonMode("formatted")}>
                Formatted
              </button>
              <button type="button" role="tab" aria-selected={jsonMode === "raw"} onClick={() => setJsonMode("raw")}>
                Raw
              </button>
            </div>
          </div>
          <div className="inspector-type">{active?.event_type ?? "No event selected"}</div>
          {active ? (
            <div className="inspector-meta">
              <Chip kind="status" status={active.status}>
                {statusLabel(active.status)}
              </Chip>
              <span>seq {active.sequence_number}</span>
              <span>{active.actor_service}</span>
            </div>
          ) : null}
        </div>
        <div className="inspector-body">
          {verification ? (
            <div className="inspector-block">
              <div className="kicker" style={{ letterSpacing: "0.14em" }}>
                Verification
              </div>
              <div className="actions">
                <button
                  type="button"
                  onClick={() => {
                    beginOperation("Integrity verification");
                    verify.mutate();
                  }}
                  disabled={actionBusy}
                >
                  {verify.isPending ? "Verifying…" : "Verify integrity"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    beginOperation("Replay");
                    replay.mutate();
                  }}
                  disabled={actionBusy}
                >
                  {replay.isPending ? "Replaying…" : "Replay"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    beginOperation("Clinical export");
                    exportClinical.mutate();
                  }}
                  disabled={actionBusy}
                >
                  {exportClinical.isPending ? "Preparing…" : "Download clinical export"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    beginOperation("Research export");
                    exportResearch.mutate();
                  }}
                  disabled={actionBusy}
                >
                  {exportResearch.isPending ? "Preparing…" : "Download research export"}
                </button>
              </div>
              <div className="dims">
                <div className="dim-row">
                  <div className="dim-key">status</div>
                  <div className="dim-val">{statusLabel(verification.status)}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">scope</div>
                  <div className="dim-val">{verification.scope.join(", ")}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">chain</div>
                  <div className="dim-val">{verification.chain_ok ? statusLabel("PASS") : statusLabel("FAILED")}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">merkle</div>
                  <div className="dim-val">{verification.merkle_ok ? statusLabel("PASS") : statusLabel("FAILED")}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">signature</div>
                  <div className="dim-val">{verification.signature_ok ? statusLabel("PASS") : statusLabel("FAILED")}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">key_id</div>
                  <div className="dim-val">{verification.key_id || "—"}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">verified_at</div>
                  <div className="dim-val">{verification.verified_at}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">content refs</div>
                  <div className="dim-val">{verification.content_ok === false ? statusLabel("FAILED") : statusLabel("PASS")}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">missing</div>
                  <div className="dim-val">{verification.missing_events.join(", ") || "none"}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">reason</div>
                  <div className="dim-val">{verification.reason || "none"}</div>
                </div>
                <div className="dim-row">
                  <div className="dim-key">hash failures</div>
                  <div className="dim-val">{verification.hash_failures.join(", ") || "none"}</div>
                </div>
              </div>
              {replay.data ? (
                <div className="replay-compare">
                  <div className="digest-note">
                    Replay {statusLabel(replay.data.result)}: original {replay.data.original_digest.slice(0, 12)}… vs {replay.data.replay_digest.slice(0, 12)}…
                    {replay.data.reasons.length ? ` (${replay.data.reasons.join("; ")})` : ""}
                  </div>
                  <div className="replay-grid">
                    <section>
                      <h3>Original output</h3>
                      <p className="digest-note">
                        {replay.data.original_digest.slice(0, 16)}
                        {replay.data.original_event_id ? ` · ${replay.data.original_event_id}` : ""}
                      </p>
                      <pre className="json">{JSON.stringify(replay.data.original_output ?? null, null, 2)}</pre>
                    </section>
                    <section>
                      <h3>Modified output</h3>
                      <p className="digest-note">
                        {replay.data.modified_event_id ? replay.data.modified_event_id : "No human modification recorded"}
                      </p>
                      <pre className="json">{JSON.stringify(replay.data.modified_output ?? null, null, 2)}</pre>
                    </section>
                    <section>
                      <h3>Replay output</h3>
                      <p className="digest-note">{replay.data.replay_digest.slice(0, 16)}</p>
                      <pre className="json">{JSON.stringify(replay.data.replay_output ?? null, null, 2)}</pre>
                    </section>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
          {active ? (
            <>
              <div className="inspector-block">
                <div className="kicker" style={{ letterSpacing: "0.14em" }}>
                  Dimensions
                </div>
                <div className="dims">
                  {dims.map(([key, value]) => (
                    <div className="dim-row" key={key}>
                      <div className="dim-key">{key}</div>
                      <div className="dim-val">{value}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div className="inspector-block json-block">
                <div className="json-head">
                  <div className="kicker" style={{ letterSpacing: "0.14em" }}>
                    Event JSON
                  </div>
                  <div className="actions" style={{ margin: 0 }}>
                    <button type="button" className={copied ? "ghost copied" : "ghost"} data-variant="ghost" onClick={copyJson}>
                      {copied ? "Copied" : "Copy"}
                    </button>
                    <button type="button" className="ghost" onClick={() => downloadJson(`event-${active.event_id}.json`, active)}>
                      Download event JSON
                    </button>
                  </div>
                </div>
                <pre className="json">{jsonMode === "formatted" ? JSON.stringify(active, null, 2) : JSON.stringify(active)}</pre>
                <div className="digest-note">
                  schema {active.schema_version} · digest {active.payload_digest ?? "none"}
                </div>
              </div>
            </>
          ) : null}
          <div className="inspector-block rationale">
            <div className="kicker" style={{ letterSpacing: "0.14em" }}>
              Structured rationale
            </div>
            {output ? (
              <>
                <p>{output.summary}</p>
                <h3>Findings</h3>
                <ul>
                  {output.findings.map((finding) => (
                    <li key={finding.text}>
                      {finding.text}{" "}
                      {finding.evidence_refs.map((ref) => (
                        <button key={ref} type="button" className="ghost evidence-btn" onClick={() => focusEvidence(ref)}>
                          {ref}
                        </button>
                      ))}
                    </li>
                  ))}
                </ul>
                <h3>Uncertainty</h3>
                <p>{output.uncertainty}</p>
                <h3>Assumptions</h3>
                <p>{output.assumptions.join("; ") || "—"}</p>
                <h3>Missing data</h3>
                <p>{output.missing_data.join("; ") || "—"}</p>
              </>
            ) : (
              <p>
                {outputQuery.isError
                  ? "Structured output requires separately authorized output access."
                  : "No structured output yet."}
              </p>
            )}
          </div>
          {overview?.human_action === "PENDING" ? (
            <div className="signoff">
              <div className="kicker" style={{ letterSpacing: "0.14em" }}>
                Sign-off
              </div>
              <textarea value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Reason for the record" />
              <div className="signoff-actions">
                <button
                  type="button"
                  data-action="ACCEPT"
                  disabled={actionBusy}
                  onClick={() => submitReview("ACCEPT")}
                >
                  {review.isPending && review.variables === "ACCEPT" ? "Accepting…" : "ACCEPT"}
                </button>
                <button
                  type="button"
                  data-action="MODIFY"
                  disabled={actionBusy}
                  onClick={() => submitReview("MODIFY")}
                >
                  {review.isPending && review.variables === "MODIFY" ? "Modifying…" : "MODIFY"}
                </button>
                <button
                  type="button"
                  data-action="REJECT"
                  disabled={actionBusy}
                  onClick={() => submitReview("REJECT")}
                >
                  {review.isPending && review.variables === "REJECT" ? "Rejecting…" : "REJECT"}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
