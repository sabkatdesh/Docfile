import { describe, expect, it } from "vitest";
import { parseRunEvent } from "./events";

const frame = (extra: object = {}) =>
  JSON.stringify({ run_id: "r1", seq: 3, ts: "t", pack_id: "supplier-pack-01", ...extra });

describe("parseRunEvent", () => {
  it("parses a known event and adds its type", () => {
    const e = parseRunEvent("pack_skipped", frame({ reason: "already on record" }));
    expect(e).toMatchObject({ type: "pack_skipped", seq: 3, reason: "already on record" });
  });

  it("ignores an event type it does not know", () => {
    expect(parseRunEvent("brand_new_event", frame())).toBeNull();
  });

  it("ignores malformed JSON", () => {
    expect(parseRunEvent("pack_started", "{nope")).toBeNull();
  });

  it("ignores a frame without a sequence number", () => {
    expect(parseRunEvent("pack_started", JSON.stringify({ run_id: "r1" }))).toBeNull();
  });

  it("ignores a body that is not an object", () => {
    expect(parseRunEvent("error", "[1,2]")).toBeNull();
  });
});
