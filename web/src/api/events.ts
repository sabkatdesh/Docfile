/** Server-sent run events. OpenAPI cannot describe an event stream, so these mirror
 * `src/docgate/workflow/runs.py` (`_execute`, `_run_pack`, `_finish`) by hand. They are the only
 * hand-written API types; everything else comes from the generated schema. */
import type { Decision } from "./types";

interface Base {
  run_id: string;
  seq: number;
  ts: string;
}

export type RunEvent =
  | (Base & { type: "run_started"; packs: string[]; total: number; resume: boolean })
  | (Base & {
      type: "pack_started";
      pack_id: string;
      index: number;
      total: number;
      steps: string[];
    })
  | (Base & {
      type: "node_completed";
      pack_id: string;
      node: string;
      ok: boolean;
      elapsed_ms: number;
      message: string | null;
    })
  | (Base & {
      type: "pack_paused";
      pack_id: string;
      machine_decision: Decision;
      reason: string;
      question: string;
    })
  | (Base & {
      type: "pack_finished";
      pack_id: string;
      decision: Decision | null;
      headline: string | null;
      primary_rule: string | null;
    })
  | (Base & { type: "pack_skipped"; pack_id: string; reason: string })
  | (Base & {
      type: "run_finished";
      status: string;
      counts: Record<string, number>;
      paused: string[];
      finished: string[];
      skipped: string[];
    })
  | (Base & { type: "error"; message: string; pack_id: string | null; fatal: boolean });

export type RunEventType = RunEvent["type"];

export const EVENT_TYPES: readonly RunEventType[] = [
  "run_started",
  "pack_started",
  "node_completed",
  "pack_paused",
  "pack_finished",
  "pack_skipped",
  "run_finished",
  "error",
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/** Parses one SSE frame. Anything malformed or of an unknown type is ignored (returns null) so a
 * newer server cannot break an older page. */
export function parseRunEvent(type: string, data: string): RunEvent | null {
  if (!(EVENT_TYPES as readonly string[]).includes(type)) return null;
  let body: unknown;
  try {
    body = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isRecord(body) || typeof body.seq !== "number" || typeof body.run_id !== "string") {
    return null;
  }
  return { ...body, type } as RunEvent;
}
