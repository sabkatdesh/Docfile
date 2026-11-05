import type { PackDetail } from "../../api/types";
import type { Mark } from "../../lib/highlight";

export const fieldMarkId = (name: string) => `field:${name}`;
export const ruleMarkId = (ruleId: string) => `rule:${ruleId}`;
export const arithmeticMarkId = (check: string) => `arith:${check}`;

/** One mark per verified quote the API could place in the text. A quote it could not place has no
 * span and so gets no mark: the page says so instead of guessing where it is. */
export function marksOf(detail: PackDetail): Mark[] {
  const marks: Mark[] = [];
  for (const f of detail.fields) {
    if (f.span) marks.push({ id: fieldMarkId(f.name), start: f.span.start, end: f.span.end });
  }
  for (const r of detail.rules) {
    if (r.span) marks.push({ id: ruleMarkId(r.rule_id), start: r.span.start, end: r.span.end });
  }
  for (const a of detail.comparison?.arithmetic ?? []) {
    if (a.span) marks.push({ id: arithmeticMarkId(a.check), start: a.span.start, end: a.span.end });
  }
  return marks;
}
