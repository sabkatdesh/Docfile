import { describe, expect, it } from "vitest";
import { parseSseText } from "./sse";

const frame = (id: number, type: string, data: object) =>
  `id: ${id}\nevent: ${type}\ndata: ${JSON.stringify({ run_id: "r", seq: id, ts: "t", ...data })}\n\n`;

describe("parseSseText", () => {
  it("parses frames in order", () => {
    const text =
      frame(1, "run_started", { packs: [], total: 0, resume: false }) +
      frame(2, "pack_skipped", { pack_id: "p", reason: "x" });
    expect(parseSseText(text).map((e) => e.type)).toEqual(["run_started", "pack_skipped"]);
  });

  it("skips keep-alive comments and unknown event types", () => {
    const text = `: keep-alive\n\n${frame(1, "something_new", {})}${frame(2, "pack_skipped", { pack_id: "p", reason: "x" })}`;
    expect(parseSseText(text).map((e) => e.seq)).toEqual([2]);
  });

  it("copes with CRLF line endings", () => {
    const text = frame(1, "pack_skipped", { pack_id: "p", reason: "x" }).replaceAll("\n", "\r\n");
    expect(parseSseText(text)).toHaveLength(1);
  });

  it("returns nothing for an empty body", () => {
    expect(parseSseText("")).toEqual([]);
  });
});
