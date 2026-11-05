import { describe, expect, it } from "vitest";
import { validateReview } from "./reviewForm";

describe("validateReview", () => {
  it.each([
    ["", "empty"],
    ["   ", "spaces"],
    ["\n\t \n", "newlines and tabs"],
  ])("blocks a blank reason (%j: %s)", (reason) => {
    const r = validateReview({ decision: "Approve", reason });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors.reason).toMatch(/reason/i);
  });

  it("requires a decision", () => {
    const r = validateReview({ decision: null, reason: "Because." });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.errors.decision).toMatch(/approve or reject/i);
  });

  it("reports both problems at once", () => {
    const r = validateReview({ decision: null, reason: " " });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(Object.keys(r.errors).sort()).toEqual(["decision", "reason"]);
  });

  it("trims the reason and passes the decision through", () => {
    expect(validateReview({ decision: "Reject", reason: "  Price too high.  " })).toEqual({
      ok: true,
      value: { decision: "Reject", reason: "Price too high." },
    });
  });
});
