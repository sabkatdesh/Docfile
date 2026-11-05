import { CircleCheck, CircleDashed, CircleX, UserSearch } from "lucide-react";
import type { Decision } from "../../api/types";
import { DECISION_TONE, type Tone } from "../../lib/verdict";

const ICON = {
  approve: CircleCheck,
  reject: CircleX,
  review: UserSearch,
} as const;

const TONE_CLASS: Record<Tone, string> = {
  approve: "bg-approve-bg text-approve-fg border-approve-line",
  reject: "bg-reject-bg text-reject-fg border-reject-line",
  review: "bg-review-bg text-review-fg border-review-line",
};

interface Props {
  decision: Decision | null;
  size?: "sm" | "lg";
}

/** Colour is never the only signal: every verdict has its own icon and its full wording. */
export function VerdictBadge({ decision, size = "sm" }: Props) {
  const pad = size === "lg" ? "px-3.5 py-1.5 text-base gap-2" : "px-2.5 py-1 text-sm gap-1.5";
  const iconSize = size === "lg" ? 20 : 16;
  if (decision === null) {
    return (
      <span
        className={`inline-flex items-center rounded-full border border-line bg-surface-2 font-medium text-muted ${pad}`}
      >
        <CircleDashed size={iconSize} aria-hidden="true" data-icon="not-run" />
        Not run
      </span>
    );
  }
  const tone = DECISION_TONE[decision];
  const Icon = ICON[tone];
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full border font-semibold ${TONE_CLASS[tone]} ${pad}`}
      data-tone={tone}
    >
      <Icon size={iconSize} aria-hidden="true" data-icon={tone} />
      {decision}
    </span>
  );
}
