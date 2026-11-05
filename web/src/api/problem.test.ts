import { describe, expect, it } from "vitest";
import {
  ApiError,
  asProblem,
  networkProblem,
  pendingPackIds,
  problemFromBody,
  problemMessage,
} from "./problem";

const body = (code: string, message: string, details: object | null = null) =>
  JSON.stringify({ error: { code, message, details } });

describe("problemFromBody", () => {
  it("reads the API error envelope", () => {
    const p = problemFromBody(409, body("run_in_progress", "wait", { run_id: "x" }));
    expect(p).toEqual({
      status: 409,
      code: "run_in_progress",
      message: "wait",
      details: { run_id: "x" },
    });
  });

  it("falls back to a generic problem for a body that is not JSON", () => {
    const p = problemFromBody(502, "<html>Bad gateway</html>");
    expect(p.code).toBe("http_error");
    expect(p.message).toContain("502");
  });

  it("falls back when the JSON is not the envelope", () => {
    expect(problemFromBody(500, '{"detail":"x"}').code).toBe("http_error");
  });
});

describe("pendingPackIds", () => {
  it("lists the packs a fresh run would discard", () => {
    const p = problemFromBody(
      409,
      body("pending_reviews_would_be_lost", "m", {
        pack_ids: ["supplier-pack-04", "supplier-pack-09"],
      }),
    );
    expect(pendingPackIds(p)).toEqual(["supplier-pack-04", "supplier-pack-09"]);
  });

  it("is null for any other problem", () => {
    expect(pendingPackIds(problemFromBody(409, body("run_in_progress", "m")))).toBeNull();
  });
});

describe("problemMessage", () => {
  it("explains a lost network in plain words", () => {
    expect(problemMessage(networkProblem())).toMatch(/could not reach the server/i);
  });

  it("explains an already-resolved review", () => {
    const p = problemFromBody(409, body("already_resolved", "raw server text"));
    expect(problemMessage(p)).toMatch(/already decided/i);
  });

  it("explains a run in progress", () => {
    expect(problemMessage(problemFromBody(409, body("run_in_progress", "x")))).toMatch(
      /in progress/i,
    );
  });

  it("counts the reviews that would be lost, with the right plural", () => {
    const one = problemFromBody(
      409,
      body("pending_reviews_would_be_lost", "m", { pack_ids: ["a"] }),
    );
    const three = problemFromBody(
      409,
      body("pending_reviews_would_be_lost", "m", { pack_ids: ["a", "b", "c"] }),
    );
    expect(problemMessage(one)).toContain("1 review still");
    expect(problemMessage(three)).toContain("3 reviews still");
  });

  it("flattens a 422 validation error into readable lines", () => {
    const p = problemFromBody(
      422,
      body("validation_error", "the request is not valid", {
        problems: [{ where: "body.reason", problem: "Field required" }],
      }),
    );
    expect(problemMessage(p)).toContain("body.reason: Field required");
  });

  it("passes through the server's message for a blank reason (invalid_review)", () => {
    const p = problemFromBody(422, body("invalid_review", "A reason is required."));
    expect(problemMessage(p)).toBe("A reason is required.");
  });

  it("uses the server's message for a code it does not know", () => {
    expect(problemMessage(problemFromBody(418, body("teapot", "I am a teapot")))).toBe(
      "I am a teapot",
    );
  });
});

describe("asProblem", () => {
  it("unwraps an ApiError", () => {
    const p = problemFromBody(404, body("unknown_pack", "m"));
    expect(asProblem(new ApiError(p))).toBe(p);
  });

  it("treats anything else (a failed fetch) as a network problem", () => {
    expect(asProblem(new TypeError("Failed to fetch")).code).toBe("network");
  });
});
