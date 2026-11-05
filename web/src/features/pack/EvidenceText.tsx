import { useEffect, useMemo, useRef } from "react";
import { buildSegments, type Mark } from "../../lib/highlight";

interface Props {
  text: string;
  marks: Mark[];
  /** The mark id the reader selected (a field, rule or arithmetic check), or null. */
  activeId: string | null;
  /** Changes on every selection, even of the same id, so the flash can replay. */
  pulse: number;
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/** The document text with every verified quote highlighted. Selecting something elsewhere on the
 * page scrolls its quote into view and flashes it. */
export function EvidenceText({ text, marks, activeId, pulse }: Props) {
  const segments = useMemo(() => buildSegments(text, marks), [text, marks]);
  const root = useRef<HTMLDivElement>(null);

  // `pulse` is the trigger: selecting the same field twice must scroll and flash twice.
  // biome-ignore lint/correctness/useExhaustiveDependencies: pulse is intentionally a trigger
  useEffect(() => {
    if (activeId === null || !root.current) return;
    const hits = root.current.querySelectorAll<HTMLElement>("mark[data-active='true']");
    const first = hits[0];
    if (!first) return;
    first.scrollIntoView({
      block: "center",
      behavior: prefersReducedMotion() ? "auto" : "smooth",
    });
    for (const el of hits) {
      el.classList.remove("flash");
      void el.offsetWidth; // restart the animation
      el.classList.add("flash");
    }
  }, [activeId, pulse]);

  let offset = 0;
  return (
    <div
      ref={root}
      className="whitespace-pre-wrap break-words font-mono text-[0.8125rem] leading-6"
      data-testid="document-text"
    >
      {segments.map((seg) => {
        const key = offset;
        offset += seg.text.length;
        if (seg.markIds.length === 0) return <span key={key}>{seg.text}</span>;
        return (
          <mark
            key={key}
            className="evidence"
            data-marks={seg.markIds.join(" ")}
            data-active={activeId !== null && seg.markIds.includes(activeId)}
          >
            {seg.text}
          </mark>
        );
      })}
    </div>
  );
}
