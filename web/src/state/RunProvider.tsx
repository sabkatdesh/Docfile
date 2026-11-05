import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";
import { api, apiUrl } from "../api/client";
import { EVENT_TYPES, parseRunEvent, type RunEvent } from "../api/events";
import { keys } from "../api/queries";
import type { RunRequest } from "../api/types";
import { initialRunState, type RunState, runReducer } from "../lib/runReducer";

export type EventSourceFactory = (url: string) => EventSource;

const STALL_MS = 20_000; // no event and no keep-alive for this long: stop trusting the stream
const POLL_MS = 2_000;
export const LAST_RUN_KEY = "docgate-last-run";

interface RunApi {
  state: RunState;
  /** True while a run is in progress on the server, whether or not this page started it. */
  active: boolean;
  /** Starts a run and begins following it. Rejects with the API's problem (e.g. the 409). */
  start: (body: RunRequest) => Promise<void>;
}

const RunContext = createContext<RunApi | null>(null);

function rememberRun(runId: string): void {
  try {
    sessionStorage.setItem(LAST_RUN_KEY, runId);
  } catch {
    // the timeline falls back to "timings not recorded"
  }
}

export function RunProvider({
  children,
  eventSourceFactory = (url) => new EventSource(url),
}: {
  children: ReactNode;
  eventSourceFactory?: EventSourceFactory;
}) {
  const [state, dispatch] = useReducer(runReducer, initialRunState);
  const client = useQueryClient();
  const source = useRef<EventSource | null>(null);
  const stall = useRef<ReturnType<typeof setTimeout> | null>(null);
  const poll = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentRun = useRef<string | null>(null);

  const refreshAll = useCallback(() => {
    for (const key of [keys.packs, keys.review, keys.eval, keys.health, ["pack"]]) {
      void client.invalidateQueries({ queryKey: key });
    }
  }, [client]);

  const stopWatching = useCallback(() => {
    source.current?.close();
    source.current = null;
    if (stall.current) clearTimeout(stall.current);
    if (poll.current) clearInterval(poll.current);
    stall.current = null;
    poll.current = null;
  }, []);

  /** The stream is gone but the run may not be. Ask the server until it says the run is over. */
  const startPolling = useCallback(
    (runId: string) => {
      source.current?.close();
      source.current = null;
      if (stall.current) clearTimeout(stall.current);
      dispatch({ kind: "connection", state: "lost" });
      if (poll.current) return;
      poll.current = setInterval(() => {
        void api
          .health()
          .then((health) => {
            void client.invalidateQueries({ queryKey: keys.packs });
            if (health.active_run_id !== runId) {
              stopWatching();
              dispatch({ kind: "ended_unseen" });
              refreshAll();
            }
          })
          .catch(() => {
            // still unreachable; keep trying
          });
      }, POLL_MS);
    },
    [client, refreshAll, stopWatching],
  );

  const handleEvent = useCallback(
    (event: RunEvent) => {
      dispatch({ kind: "server", event });
      if (event.type === "pack_finished" || event.type === "pack_paused") {
        void client.invalidateQueries({ queryKey: keys.packs });
        void client.invalidateQueries({ queryKey: keys.review });
      }
      if (event.type === "run_finished" || (event.type === "error" && event.fatal)) {
        // The stream is finite; closing it stops EventSource from reconnecting for nothing.
        if (event.type === "run_finished") stopWatching();
        refreshAll();
      }
    },
    [client, refreshAll, stopWatching],
  );

  const attach = useCallback(
    (runId: string, eventsUrl: string) => {
      stopWatching();
      currentRun.current = runId;
      rememberRun(runId);
      dispatch({ kind: "begin", runId });
      const es = eventSourceFactory(apiUrl(eventsUrl));
      source.current = es;

      const armStall = () => {
        if (stall.current) clearTimeout(stall.current);
        stall.current = setTimeout(() => startPolling(runId), STALL_MS);
      };
      armStall();

      es.onopen = () => {
        dispatch({ kind: "connection", state: "open" });
        armStall();
      };
      for (const type of EVENT_TYPES) {
        es.addEventListener(type, (raw) => {
          // The server's own `error` event carries data. The browser's connection error does not.
          if (!(raw instanceof MessageEvent) || typeof raw.data !== "string") {
            if (type === "error") onConnectionError();
            return;
          }
          armStall();
          const event = parseRunEvent(type, raw.data);
          if (event) handleEvent(event);
        });
      }
      // Keep-alive comments are invisible to EventSource, so a quiet stream looks stalled only
      // after STALL_MS; the server sends one every 15 s.
      function onConnectionError() {
        if (es.readyState === 2 /* CLOSED */) startPolling(runId);
        else dispatch({ kind: "connection", state: "reconnecting" });
      }
    },
    [eventSourceFactory, handleEvent, startPolling, stopWatching],
  );

  // After a page reload, pick up a run that is still going.
  useEffect(() => {
    let cancelled = false;
    void api
      .health()
      .then((health) => {
        if (!cancelled && health.active_run_id && currentRun.current === null) {
          attach(health.active_run_id, `/api/runs/${health.active_run_id}/events`);
        }
      })
      .catch(() => {
        // the dashboard shows its own error state
      });
    return () => {
      cancelled = true;
    };
  }, [attach]);

  useEffect(() => stopWatching, [stopWatching]);

  const start = useCallback(
    async (body: RunRequest) => {
      const accepted = await api.startRun(body);
      attach(accepted.run_id, accepted.events_url);
    },
    [attach],
  );

  const value = useMemo<RunApi>(
    () => ({ state, active: state.status === "running", start }),
    [state, start],
  );
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun(): RunApi {
  const value = useContext(RunContext);
  if (!value) throw new Error("useRun needs a RunProvider");
  return value;
}
