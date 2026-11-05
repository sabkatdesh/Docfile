import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { contrast } from "./contrast";

const css = readFileSync(resolve(process.cwd(), "src/index.css"), "utf-8");

/** Token map of the block that starts at `opener` (e.g. ':root {'). */
function block(opener: string): Record<string, string> {
  const start = css.indexOf(opener);
  if (start < 0) throw new Error(`no block ${opener}`);
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    out[m[1] as string] = m[2] as string;
  }
  return out;
}

const light = block(":root {");
const dark = block(':root[data-theme="dark"] {');
const darkByPreference = block(':root:not([data-theme="light"]) {');

// [foreground token, background token, minimum ratio]. Text needs 4.5; borders of controls 3.
const TEXT = 4.5;
const UI = 3;
const PAIRS: [string, string, number][] = [
  ["fg", "bg", TEXT],
  ["fg", "surface", TEXT],
  ["fg", "surface-2", TEXT],
  ["muted", "bg", TEXT],
  ["muted", "surface", TEXT],
  ["muted", "surface-2", TEXT],
  ["accent-text", "bg", TEXT],
  ["accent-text", "surface", TEXT],
  ["accent-fg", "accent-bg", TEXT],
  ["approve-fg", "approve-bg", TEXT],
  ["reject-fg", "reject-bg", TEXT],
  ["review-fg", "review-bg", TEXT],
  ["mark-fg", "mark-bg", TEXT],
  ["mark-fg", "mark-active-bg", TEXT],
  ["control-border", "surface", UI],
  ["control-border", "bg", UI],
];

describe.each([
  ["light", light],
  ["dark", dark],
])("%s theme contrast (WCAG AA)", (_name, tokens) => {
  it.each(PAIRS)("%s on %s is at least %s:1", (fg, bg, min) => {
    const a = tokens[fg];
    const b = tokens[bg];
    expect(a, `token --${fg}`).toBeDefined();
    expect(b, `token --${bg}`).toBeDefined();
    expect(contrast(a as string, b as string)).toBeGreaterThanOrEqual(min);
  });
});

describe("dark theme tokens", () => {
  it("are identical whether chosen by the toggle or by the system preference", () => {
    expect(darkByPreference).toEqual(dark);
  });
});
