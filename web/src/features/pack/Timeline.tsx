import { useQuery } from "@tanstack/react-query";
import { Check, CircleDashed, X } from "lucide-react";
import { fetchRunEventsText } from "../../api/client";
import type { PackDetail } from "../../api/types";
import { formatMs } from "../../lib/format";
import { initialRunState, type PackProgress, runReducer } from "../../lib/runReducer";
import { parseSseText } from "../../lib/sse";
import { DEFAULT_STEPS, stepLabel } from "../../lib/steps";
import { LAST_RUN_KEY, useRun } from "../../state/RunProvider";

function lastRunId(): string | null {
  try {
    return sessionStorage.getItem(LAST_RUN_KEY);
  } catch {
    return null;
  }
}

/** Timings are not stored with a pack, only in the run's event log, so rebuild them from it. */
function useRecordedProgress(packId: string): PackProgress | null {
  const { state } = useRun();
  const live = state.packs[packId];
  const hasLive = live !== undefined && Object.keys(live.stepElapsed).length > 0;
  const runId = lastRunId();
  const replay = useQuery({
    queryKey: ["run-events", runId],
    enabled: !hasLive && runId !== null,
    retry: false,
    staleTime: Number.POSITIVE_INFINITY,
    queryFn: async () => {
      const events = parseSseText(await fetchRunEventsText(`/api/runs/${runId}/events`));
      return events.reduce((s, event) => runReducer(s, { kind: "server", event }), initialRunState);
    },
  });
  if (hasLive) return live;
  return replay.data?.packs[packId] ?? null;
}

export function Timeline({ detail }: { detail: PackDetail }) {
  const recorded = useRecordedProgress(detail.pack_id);
  const steps = recorded && recorded.steps.length > 0 ? recorded.steps : [...DEFAULT_STEPS];
  const failed = new Set(detail.errors.map((e) => e.node));
  let previous = 0;

  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        {recorded
          ? "What the checker did, in order, and how long each step took."
          : "Timings were not recorded for this pack (they are kept only for the latest run)."}
      </p>
      <ol className="divide-y divide-line rounded-lg border border-line">
        {steps.map((step) => {
          const at = recorded?.stepElapsed[step];
          const took = at === undefined ? null : Math.max(0, at - previous);
          if (at !== undefined) previous = at;
          const bad = failed.has(step) || recorded?.failedStep === step;
          const Icon = bad ? X : at !== undefined || !recorded ? Check : CircleDashed;
          return (
            <li key={step} className="flex items-center gap-3 px-4 py-2.5">
              <Icon
                size={18}
                aria-hidden="true"
                className={bad ? "text-reject-fg" : "text-approve-fg"}
              />
              <span className="flex-1">
                {stepLabel(step)}
                {bad ? <span className="sr-only"> (failed)</span> : null}
              </span>
              <span className="tabular text-sm text-muted">
                {took === null ? "" : formatMs(took)}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
