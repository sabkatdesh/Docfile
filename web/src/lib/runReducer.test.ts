import { describe, expect, it } from "vitest";
import type { RunEvent } from "../api/events";
import { initialRunState, type RunState, runReducer } from "./runReducer";

let seq = 0;
const base = () => ({ run_id: "r1", seq: ++seq, ts: "2026-11-06T00:00:00Z" });
const STEPS = ["ingest", "extract_llm", "reconcile", "report"];
const P1 = "supplier-pack-01";
const P2 = "supplier-pack-02";

const started = (packs = [P1, P2]): RunEvent => ({
  ...base(),
  type: "run_started",
  packs,
  total: packs.length,
  resume: false,
});
const packStarted = (pack_id: string, index = 1): RunEvent => ({
  ...base(),
  type: "pack_started",
  pack_id,
  index,
  total: 2,
  steps: STEPS,
});
const node = (pack_id: string, n: string, ok = true, elapsed_ms = 10): RunEvent => ({
  ...base(),
  type: "node_completed",
  pack_id,
  node: n,
  ok,
  elapsed_ms,
  message: ok ? null : "boom",
});
const finishedPack = (pack_id: string): RunEvent => ({
  ...base(),
  type: "pack_finished",
  pack_id,
  decision: "Approve",
  headline: "All checks passed",
  primary_rule: null,
});
const runFinished = (status = "completed"): RunEvent => ({
  ...base(),
  type: "run_finished",
  status,
  counts: { Approve: 2 },
  paused: [],
  finished: [P1, P2],
  skipped: [],
});

const fold = (events: RunEvent[], from: RunState = initialRunState): RunState =>
  events.reduce((s, event) => runReducer(s, { kind: "server", event }), from);

describe("runReducer", () => {
  it("starts idle", () => {
    expect(initialRunState.status).toBe("idle");
  });

  it("run_started queues every pack and counts them", () => {
    const s = fold([started()]);
    expect(s.status).toBe("running");
    expect(s.total).toBe(2);
    expect(s.packs[P1]?.phase).toBe("queued");
    expect(s.order).toEqual([P1, P2]);
  });

  it("pack_started marks a pack running with its steps", () => {
    const p = fold([started(), packStarted(P1)]).packs[P1];
    expect(p?.phase).toBe("running");
    expect(p?.steps).toEqual(STEPS);
    expect(p?.current).toBe("ingest");
  });

  it("node_completed advances the current step and records the time", () => {
    const p = fold([started(), packStarted(P1), node(P1, "ingest", true, 120)]).packs[P1];
    expect(p?.done).toEqual(["ingest"]);
    expect(p?.current).toBe("extract_llm");
    expect(p?.elapsedMs).toBe(120);
    expect(p?.stepElapsed).toEqual({ ingest: 120 });
  });

  it("a failed node is remembered as failed", () => {
    const p = fold([started(), packStarted(P1), node(P1, "extract_llm", false)]).packs[P1];
    expect(p?.failedStep).toBe("extract_llm");
  });

  it("pack_paused waits for a person and keeps the machine decision", () => {
    const s = fold([
      started(),
      packStarted(P1),
      {
        ...base(),
        type: "pack_paused",
        pack_id: P1,
        machine_decision: "Needs a person to check",
        reason: "H1",
        question: "?",
      },
    ]);
    expect(s.packs[P1]?.phase).toBe("paused");
    expect(s.packs[P1]?.decision).toBe("Needs a person to check");
    expect(s.settled).toBe(1);
  });

  it("pack_finished stores the decision and headline", () => {
    const s = fold([started(), packStarted(P1), finishedPack(P1)]);
    expect(s.packs[P1]?.phase).toBe("done");
    expect(s.packs[P1]?.decision).toBe("Approve");
    expect(s.packs[P1]?.headline).toBe("All checks passed");
    expect(s.settled).toBe(1);
  });

  it("pack_skipped settles a pack without running it", () => {
    const s = fold([
      started(),
      { ...base(), type: "pack_skipped", pack_id: P1, reason: "already on record" },
    ]);
    expect(s.packs[P1]?.phase).toBe("skipped");
    expect(s.settled).toBe(1);
  });

  it("run_finished ends the run with the counts", () => {
    const s = fold([started(), runFinished()]);
    expect(s.status).toBe("finished");
    expect(s.counts).toEqual({ Approve: 2 });
  });

  it("run_finished with a failed status is a failure", () => {
    expect(fold([started(), runFinished("failed")]).status).toBe("failed");
  });

  it("a fatal error event fails the run and keeps the message", () => {
    const s = fold([
      started(),
      { ...base(), type: "error", message: "bad key", pack_id: null, fatal: true },
    ]);
    expect(s.status).toBe("failed");
    expect(s.error).toBe("bad key");
  });

  it("ends a full realistic run as finished with every pack done", () => {
    const events: RunEvent[] = [started()];
    for (const [i, id] of [P1, P2].entries()) {
      events.push(packStarted(id, i + 1));
      for (const n of STEPS) events.push(node(id, n));
      events.push(finishedPack(id));
    }
    events.push(runFinished());
    const s = fold(events);
    expect(s.status).toBe("finished");
    expect(s.settled).toBe(2);
    expect(Object.values(s.packs).every((p) => p.phase === "done")).toBe(true);
  });

  it("ignores an event it has already seen (replay after a reconnect)", () => {
    const e = packStarted(P1);
    const once = fold([started(), e]);
    expect(runReducer(once, { kind: "server", event: e })).toBe(once);
  });

  it("ignores an older event that arrives late", () => {
    const late = node(P1, "ingest");
    const s = fold([started(), packStarted(P1), node(P1, "reconcile")]);
    expect(runReducer(s, { kind: "server", event: { ...late, seq: 1 } })).toBe(s);
  });

  it("creates a pack row if events arrive for one it never saw queued", () => {
    expect(fold([packStarted("supplier-pack-09")]).packs["supplier-pack-09"]?.phase).toBe(
      "running",
    );
  });

  it("tracks the connection without losing progress", () => {
    const s = fold([started(), packStarted(P1)]);
    const lost = runReducer(s, { kind: "connection", state: "reconnecting" });
    expect(lost.connection).toBe("reconnecting");
    expect(lost.packs).toBe(s.packs);
    expect(runReducer(lost, { kind: "connection", state: "open" }).connection).toBe("open");
  });

  it("does not show a stale connection warning once the run has finished", () => {
    const s = fold([started(), runFinished()]);
    expect(runReducer(s, { kind: "connection", state: "reconnecting" }).connection).toBe("open");
  });

  it("begin resets to a fresh running state for a new run id", () => {
    const old = fold([started(), runFinished()]);
    const s = runReducer(old, { kind: "begin", runId: "r2" });
    expect(s.status).toBe("running");
    expect(s.runId).toBe("r2");
    expect(s.packs).toEqual({});
    expect(s.lastSeq).toBe(0);
  });

  it("ended-while-disconnected is its own status, never a success", () => {
    const s = fold([started(), packStarted(P1)]);
    expect(runReducer(s, { kind: "ended_unseen" }).status).toBe("lost");
  });
});
