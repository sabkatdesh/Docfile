/** Display helpers. Amounts arrive as Decimal strings; they are only re-spaced here, never turned
 * into floating point, so no digit can change on the way to the screen. */

/** "322000.00" -> "322,000.00". Anything that is not a plain decimal is returned untouched. */
export function groupDigits(value: string): string {
  const m = /^(-?)(\d+)(\.\d+)?$/.exec(value.trim());
  if (!m) return value;
  const [, sign = "", whole = "", fraction = ""] = m;
  return `${sign}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction}`;
}

/** "2.31" -> "+2.31%", "-1.54" -> "−1.54%", "0.00" -> "0.00%". */
export function formatDelta(value: string | null): string {
  if (value === null) return "–";
  const n = value.trim();
  if (!/^-?\d+(\.\d+)?$/.test(n)) return value;
  const isZero = /^-?0+(\.0+)?$/.test(n);
  if (isZero) return `${n.replace("-", "")}%`;
  return n.startsWith("-") ? `−${n.slice(1)}%` : `+${n}%`;
}

/** The table shows a short reason; the evidence quote has its own place on the pack page. */
export function shortReason(headline: string | null): string {
  if (!headline) return "";
  return headline.replace(/\s*\[evidence:(?:[^\]"]|"[^"]*")*\]/g, "").replace(/\s+([.;,])/g, "$1");
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatMs(ms: number): string {
  return ms < 1000 ? `${Math.max(0, Math.round(ms))} ms` : `${(ms / 1000).toFixed(1)} s`;
}
