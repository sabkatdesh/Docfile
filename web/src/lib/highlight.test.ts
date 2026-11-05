import { describe, expect, it } from "vitest";
import { buildSegments, type Mark } from "./highlight";

const joined = (text: string, marks: Mark[]) =>
  buildSegments(text, marks)
    .map((s) => s.text)
    .join("");

const ids = (text: string, marks: Mark[]) =>
  buildSegments(text, marks).map((s) => [s.text, s.markIds]);

describe("buildSegments", () => {
  it("returns one plain segment when there are no marks", () => {
    expect(ids("hello", [])).toEqual([["hello", []]]);
  });

  it("returns nothing for empty text", () => {
    expect(buildSegments("", [{ id: "a", start: 0, end: 0 }])).toEqual([]);
  });

  it("marks a single span in the middle", () => {
    expect(ids("abcdef", [{ id: "a", start: 2, end: 4 }])).toEqual([
      ["ab", []],
      ["cd", ["a"]],
      ["ef", []],
    ]);
  });

  it("handles a quote at the very start of the text", () => {
    expect(ids("abcdef", [{ id: "a", start: 0, end: 3 }])).toEqual([
      ["abc", ["a"]],
      ["def", []],
    ]);
  });

  it("handles a quote at the very end of the text", () => {
    expect(ids("abcdef", [{ id: "a", start: 3, end: 6 }])).toEqual([
      ["abc", []],
      ["def", ["a"]],
    ]);
  });

  it("handles a quote that is the whole text", () => {
    expect(ids("abc", [{ id: "a", start: 0, end: 3 }])).toEqual([["abc", ["a"]]]);
  });

  it("keeps adjacent spans separate with no gap and no overlap", () => {
    const marks = [
      { id: "a", start: 0, end: 3 },
      { id: "b", start: 3, end: 6 },
    ];
    expect(ids("abcdef", marks)).toEqual([
      ["abc", ["a"]],
      ["def", ["b"]],
    ]);
  });

  it("carries both ids where two spans overlap", () => {
    const marks = [
      { id: "a", start: 0, end: 4 },
      { id: "b", start: 2, end: 6 },
    ];
    expect(ids("abcdef", marks)).toEqual([
      ["ab", ["a"]],
      ["cd", ["a", "b"]],
      ["ef", ["b"]],
    ]);
  });

  it("handles a span nested inside another", () => {
    const marks = [
      { id: "outer", start: 0, end: 6 },
      { id: "inner", start: 2, end: 4 },
    ];
    expect(ids("abcdef", marks)).toEqual([
      ["ab", ["outer"]],
      ["cd", ["outer", "inner"]],
      ["ef", ["outer"]],
    ]);
  });

  it("gives identical spans (the same quote used twice) both ids", () => {
    const marks = [
      { id: "field:qty", start: 1, end: 3 },
      { id: "rule:H2", start: 1, end: 3 },
    ];
    expect(ids("abcd", marks)).toEqual([
      ["a", []],
      ["bc", ["field:qty", "rule:H2"]],
      ["d", []],
    ]);
  });

  it("drops spans that cannot be placed instead of guessing", () => {
    const bad: Mark[] = [
      { id: "empty", start: 2, end: 2 },
      { id: "inverted", start: 4, end: 1 },
      { id: "negative", start: -1, end: 2 },
      { id: "past-end", start: 3, end: 99 },
      { id: "fraction", start: 0.5, end: 2 },
    ];
    expect(ids("abcd", bad)).toEqual([["abcd", []]]);
  });

  it("counts offsets in code points, so astral characters do not shift the span", () => {
    // "😀" is one code point (2 UTF-16 units). The API counts code points.
    const text = "😀 price 6.40";
    const start = Array.from("😀 price ").length;
    const end = start + Array.from("6.40").length;
    expect(ids(text, [{ id: "a", start, end }])).toEqual([
      ["😀 price ", []],
      ["6.40", ["a"]],
    ]);
  });

  it("can mark an astral character itself and never splits its surrogate pair", () => {
    const text = "a😀b";
    expect(ids(text, [{ id: "e", start: 1, end: 2 }])).toEqual([
      ["a", []],
      ["😀", ["e"]],
      ["b", []],
    ]);
  });

  it("works with combining marks and CJK", () => {
    const text = "東京 café ₹5"; // "é" written as e + U+0301
    const cafe = "café";
    const full = `東京 ${cafe} ₹5`;
    const start = Array.from("東京 ").length;
    const end = start + Array.from(cafe).length;
    expect(ids(full, [{ id: "a", start, end }])[1]).toEqual([cafe, ["a"]]);
    expect(text.length).toBeGreaterThan(0);
  });

  it("always reproduces the original text exactly, for random spans", () => {
    const text = "Unit price: 6.40 😀 per kg\nQty 50,000 – total 322,000 ৳";
    const n = Array.from(text).length;
    let seed = 7;
    const rand = (max: number) => {
      seed = (seed * 1103515245 + 12345) & 0x7fffffff;
      return seed % max;
    };
    for (let round = 0; round < 200; round++) {
      const marks: Mark[] = Array.from({ length: 1 + rand(5) }, (_, i) => {
        const a = rand(n + 3) - 1;
        return { id: `m${i}`, start: a, end: a + rand(12) };
      });
      expect(joined(text, marks)).toBe(text);
    }
  });
});
