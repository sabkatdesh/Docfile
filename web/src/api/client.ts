import { ApiError, networkProblem, problemFromBody } from "./problem";
import type {
  EvalView,
  Health,
  PackDetail,
  PackListItem,
  PendingReviewItem,
  ReviewRequest,
  RunAccepted,
  RunRequest,
} from "./types";

let base = "";

/** Same-origin by default (the API serves the page, and Vite proxies /api in development).
 * Tests that talk to a separate server set an absolute base. */
export function setApiBase(url: string): void {
  base = url.replace(/\/+$/, "");
}

export const apiUrl = (path: string): string => `${base}${path}`;

async function request<T>(path: string, init?: { method: string; body: unknown }): Promise<T> {
  let res: Response;
  try {
    res = await fetch(apiUrl(path), {
      method: init?.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(init ? { "Content-Type": "application/json" } : {}),
      },
      body: init ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError(networkProblem());
  }
  const text = await res.text();
  if (!res.ok) throw new ApiError(problemFromBody(res.status, text));
  return JSON.parse(text) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  packs: () => request<PackListItem[]>("/api/packs"),
  pack: (id: string) => request<PackDetail>(`/api/packs/${encodeURIComponent(id)}`),
  review: () => request<PendingReviewItem[]>("/api/review"),
  eval: () => request<EvalView>("/api/eval"),
  startRun: (body: RunRequest) => request<RunAccepted>("/api/runs", { method: "POST", body }),
  resolve: (packId: string, body: ReviewRequest) =>
    request<PackListItem>(`/api/review/${encodeURIComponent(packId)}`, { method: "POST", body }),
};

/** Raw text of a run's (finite) event stream, for rebuilding a timeline after the fact. */
export async function fetchRunEventsText(eventsUrl: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(apiUrl(eventsUrl), { headers: { Accept: "text/event-stream" } });
  } catch {
    throw new ApiError(networkProblem());
  }
  const text = await res.text();
  if (!res.ok) throw new ApiError(problemFromBody(res.status, text));
  return text;
}
