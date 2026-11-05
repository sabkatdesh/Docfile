import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { vi } from "vitest";
import { makeQueryClient, Providers, routes } from "../App";
import blankReason from "./fixtures/error-blank-reason.json";
import evalView from "./fixtures/eval.json";
import health from "./fixtures/health.json";
import pack04 from "./fixtures/pack-04.json";
import pack09 from "./fixtures/pack-09.json";
import packs from "./fixtures/packs-after-run.json";
import review from "./fixtures/review.json";

export { blankReason, evalView, health, pack04, pack09, packs, review };

export interface Call {
  method: string;
  path: string;
  body: unknown;
}

export type Responder = (call: Call) => { status?: number; body: unknown } | undefined;

/** Stubs `fetch` with canned API responses, keyed by method and path. Anything unmatched is a
 * test bug, so it fails loudly instead of returning something plausible. */
export function stubApi(overrides: Responder = () => undefined) {
  const calls: Call[] = [];
  const fetchStub = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input).replace(/^https?:\/\/[^/]+/, "");
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    const call: Call = { method, path, body };
    calls.push(call);
    const custom = overrides(call);
    const found =
      custom ??
      (method === "GET" && path === "/api/health"
        ? { body: health }
        : method === "GET" && path === "/api/packs"
          ? { body: packs }
          : method === "GET" && path === "/api/review"
            ? { body: review }
            : method === "GET" && path === "/api/eval"
              ? { body: evalView }
              : method === "GET" && path === "/api/packs/supplier-pack-09"
                ? { body: pack09 }
                : undefined);
    if (!found) throw new Error(`unexpected request: ${method} ${path}`);
    const text = JSON.stringify(found.body);
    return new Response(text, {
      status: found.status ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchStub);
  return { calls, fetchStub };
}

export function renderApp(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const queryClient = makeQueryClient();
  queryClient.setDefaultOptions({ queries: { retry: false } });
  // A stream that never delivers anything: these tests are about the pages, not the stream.
  const eventSourceFactory = () =>
    ({
      addEventListener: () => {},
      close: () => {},
      readyState: 1,
      onopen: null,
    }) as unknown as EventSource;
  return render(
    <Providers queryClient={queryClient} eventSourceFactory={eventSourceFactory}>
      <RouterProvider router={router} />
    </Providers>,
  );
}
