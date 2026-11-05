import { Check, CircleHelp, X } from "lucide-react";
import type { RuleStatus } from "../../api/types";
import { RULE_STATUS_LABEL } from "../../lib/verdict";

const STYLE: Record<RuleStatus, { cls: string; Icon: typeof Check }> = {
  PASS: { cls: "bg-approve-bg text-approve-fg border-approve-line", Icon: Check },
  FAIL: { cls: "bg-reject-bg text-reject-fg border-reject-line", Icon: X },
  UNKNOWN: { cls: "bg-review-bg text-review-fg border-review-line", Icon: CircleHelp },
};

export function RuleStatusBadge({ status }: { status: RuleStatus }) {
  const { cls, Icon } = STYLE[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${cls}`}
    >
      <Icon size={14} aria-hidden="true" data-icon={status.toLowerCase()} />
      {RULE_STATUS_LABEL[status]}
    </span>
  );
}
