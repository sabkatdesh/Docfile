import { describe, expect, it } from "vitest";
import { formatDelta, formatMs, groupDigits, shortReason } from "./format";

describe("groupDigits", () => {
  it.each([
    ["322000.00", "322,000.00"],
    ["6.40", "6.40"],
    ["50000", "50,000"],
    ["1234567.891", "1,234,567.891"],
    ["-12000.5", "-12,000.5"],
    ["0", "0"],
  ])("%s -> %s", (input, expected) => expect(groupDigits(input)).toBe(expected));

  it("leaves text that is not a plain decimal alone", () => {
    expect(groupDigits("30-90 days")).toBe("30-90 days");
    expect(groupDigits("A-1")).toBe("A-1");
  });
});

describe("formatDelta", () => {
  it("signs a rise and a fall, with a real minus sign", () => {
    expect(formatDelta("2.31")).toBe("+2.31%");
    expect(formatDelta("-1.54")).toBe("−1.54%");
  });
  it("shows zero without a sign", () => {
    expect(formatDelta("0.00")).toBe("0.00%");
    expect(formatDelta("-0.00")).toBe("0.00%");
  });
  it("shows a dash when there is no value", () => {
    expect(formatDelta(null)).toBe("–");
  });
});

describe("shortReason", () => {
  it("drops the trailing evidence quote", () => {
    expect(
      shortReason(
        'Rejected because R2 (Advance payment more than 20%): advance 40% is more than 20% [evidence: "1. Payment. 40% advance."].',
      ),
    ).toBe("Rejected because R2 (Advance payment more than 20%): advance 40% is more than 20%.");
  });
  it("drops every evidence quote when a pack fails more than one rule", () => {
    const out = shortReason(
      'A person must check: H3 (x): a [evidence: "q1"]; H6 (y): b [evidence: "q2"].',
    );
    expect(out).toBe("A person must check: H3 (x): a; H6 (y): b.");
  });
  it("drops evidence that is a plain note rather than a quote", () => {
    expect(
      shortReason(
        "Rejected because R3 (No late-delivery penalty): no clause found [evidence: not found in the document].",
      ),
    ).toBe("Rejected because R3 (No late-delivery penalty): no clause found.");
  });
  it("keeps going when a quote itself contains a closing bracket", () => {
    expect(shortReason('Bad [evidence: "a ] b"] and more.')).toBe("Bad and more.");
  });
  it("keeps text that has no evidence", () => {
    expect(shortReason("All 12 checks passed.")).toBe("All 12 checks passed.");
  });
  it("copes with a missing headline", () => {
    expect(shortReason(null)).toBe("");
  });
});

describe("formatMs", () => {
  it("uses ms under a second and seconds above", () => {
    expect(formatMs(420)).toBe("420 ms");
    expect(formatMs(1500)).toBe("1.5 s");
  });
});
