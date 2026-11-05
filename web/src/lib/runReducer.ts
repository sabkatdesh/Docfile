import type { RunEvent } from "../api/events";
import type { Decision } from "../api/types";

export type RunStatus = "idle" | "running" | "finished" | "failed" | "lost";
export type Connection = "open" | "reconnecting" | "lost";
export type PackPhase = "queued" | "running" | "paused" | "done" | "skipped" | "failed";

export interface PackProgress {
  phase: PackPhase;
  steps: string[];
  done: string[];
  current: string | null;
  failedStep: string | null;
  decision: Decision | null;
  headline: string | null;
  elapsedMs: number;
  /** Cumulative elapsed time at the moment each step finished, for the timeline. */
  stepElapsed: Record<string, number>;
}

export interface RunState {
  status: RunStatus;
  connection: Connection;
  runId: string | null;
  total: number;
  /** Packs that no longer need the run's attention: finished, paused for a person, or skipped. */
  settled: number;
  order: string[];
  packs: Record<string, PackProgress>;
  counts: Record<string, number>;
  lastSeq: number;
  error: string | null;
}

export type RunAction =
  | { kind: "server"; event: RunEvent }
  | { kind: "connection"; state: Connection }
  | { kind: "begin"; runId: string }
  | { kind: "ended_unseen" }
  | { kind: "reset" };

export const initialRunState: RunState = {
  status: "idle",
  connection: "open",
  runId: null,
  total: 0,
  settled: 0,
  order: [],
  packs: {},
  counts: {},
  lastSeq: 0,
  error: null,
};

const blankPack = (): PackProgress => ({
  phase: "queued",
  steps: [],
  done: [],
  current: null,
  failedStep: null,
  decision: null,
  headline: null,
  elapsedMs: 0,
  stepElapsed: {},
});

const SETTLED: readonly PackPhase[] = ["done", "paused", "skipped", "failed"];

function withPack(
  state: RunState,
  id: string,
  change: (p: PackProgress) => PackProgress,
): RunState {
  const before = state.packs[id] ?? blankPack();
  const after = change(before);
  const wasSettled = SETTLED.includes(before.phase);
  const nowSettled = SETTLED.includes(after.phase);
  const delta = nowSettled === wasSettled ? 0 : nowSettled ? 1 : -1;
  return {
    ...state,
    order: state.order.includes(id) ? state.order : [...state.order, id],
    packs: { ...state.packs, [id]: after },
    settled: state.settled + delta,
  };
}

function apply(state: RunState, event: RunEvent): RunState {
  switch (event.type) {
    case "run_started":
      return {
        ...state,
        status: "running",
        runId: event.run_id,
        total: event.total,
        order: event.packs,
        packs: Object.fromEntries(event.packs.map((id) => [id, blankPack()])),
        settled: 0,
        counts: {},
        error: null,
      };
    case "pack_started":
      return withPack(state, event.pack_id, (p) => ({
        ...p,
        phase: "running",
        steps: event.steps,
        done: [],
        current: event.steps[0] ?? null,
      }));
    case "node_completed":
      return withPack(state, event.pack_id, (p) => {
        const at = p.steps.indexOf(event.node);
        const next = at >= 0 ? (p.steps[at + 1] ?? null) : p.current;
        return {
          ...p,
          done: p.done.includes(event.node) ? p.done : [...p.done, event.node],
          current: next,
          failedStep: event.ok ? p.failedStep : event.node,
          elapsedMs: event.elapsed_ms,
          stepElapsed: { ...p.stepElapsed, [event.node]: event.elapsed_ms },
        };
      });
    case "pack_paused":
      return withPack(state, event.pack_id, (p) => ({
        ...p,
        phase: "paused",
        current: "human_gate",
        decision: event.machine_decision,
        headline: event.reason,
      }));
    case "pack_finished":
      return withPack(state, event.pack_id, (p) => ({
        ...p,
        phase: "done",
        current: null,
        decision: event.decision,
        headline: event.headline,
      }));
    case "pack_skipped":
      return withPack(state, event.pack_id, (p) => ({ ...p, phase: "skipped" }));
    case "run_finished":
      return {
        ...state,
        status: event.status === "completed" ? "finished" : "failed",
        connection: "open",
        counts: event.counts,
      };
    case "error":
      return event.fatal
        ? { ...state, status: "failed", error: event.message }
        : { ...state, error: event.message };
  }
}

export function runReducer(state: RunState, action: RunAction): RunState {
  switch (action.kind) {
    case "server": {
      // The server numbers events 1..n. Anything at or below what we have seen is a replay.
      if (action.event.seq <= state.lastSeq) return state;
      return { ...apply(state, action.event), lastSeq: action.event.seq };
    }
    case "connection": {
      const over = state.status === "finished" || state.status === "failed";
      const connection = over ? "open" : action.state;
      return connection === state.connection ? state : { ...state, connection };
    }
    case "begin":
      return { ...initialRunState, status: "running", runId: action.runId };
    case "ended_unseen":
      return { ...state, status: "lost", connection: "open" };
    case "reset":
      return initialRunState;
  }
}
