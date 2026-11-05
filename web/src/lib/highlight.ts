/** Splits a document into plain and highlighted pieces.
 *
 * The API reports where each verified quote sits as half-open ranges of Python string indices,
 * which count Unicode code points. JavaScript strings count UTF-16 units, so the two disagree as
 * soon as the text holds an emoji or other astral character. This module is the one place that
 * converts, so nothing else slices the text by an API offset.
 */

export interface Mark {
  id: string;
  /** Code-point offsets, start inclusive, end exclusive. */
  start: number;
  end: number;
}

export interface Segment {
  text: string;
  /** Every mark that covers this piece, in input order. Empty for plain text. */
  markIds: string[];
}

/** unit[i] is the UTF-16 offset of code point i; the last entry is the full length. */
function codePointOffsets(text: string): number[] {
  const offsets: number[] = [];
  let unit = 0;
  for (const ch of text) {
    offsets.push(unit);
    unit += ch.length;
  }
  offsets.push(unit);
  return offsets;
}

function isPlaceable(mark: Mark, codePoints: number): boolean {
  const { start, end } = mark;
  return (
    Number.isInteger(start) &&
    Number.isInteger(end) &&
    start >= 0 &&
    start < end &&
    end <= codePoints
  );
}

export function buildSegments(text: string, marks: readonly Mark[]): Segment[] {
  if (text === "") return [];
  const offsets = codePointOffsets(text);
  const codePoints = offsets.length - 1;
  // A span that cannot be placed is dropped, never clamped: a wrong highlight is worse than none.
  const placed = marks
    .filter((m) => isPlaceable(m, codePoints))
    .map((m) => ({ id: m.id, start: offsets[m.start] as number, end: offsets[m.end] as number }));

  const cuts = new Set<number>([0, text.length]);
  for (const m of placed) {
    cuts.add(m.start);
    cuts.add(m.end);
  }
  const bounds = [...cuts].sort((a, b) => a - b);

  const segments: Segment[] = [];
  for (let i = 0; i < bounds.length - 1; i++) {
    const from = bounds[i] as number;
    const to = bounds[i + 1] as number;
    segments.push({
      text: text.slice(from, to),
      markIds: placed.filter((m) => m.start <= from && m.end >= to).map((m) => m.id),
    });
  }
  return segments;
}
