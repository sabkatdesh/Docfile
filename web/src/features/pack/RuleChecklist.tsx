import { MapPin } from "lucide-react";
import type { RuleDetail } from "../../api/types";
import { RuleStatusBadge } from "../../components/ui/RuleStatusBadge";
import { ruleMarkId } from "./marks";

interface Props {
  rules: RuleDetail[];
  onSelect: (markId: string) => void;
}

function Group({
  title,
  hint,
  rules,
  onSelect,
}: {
  title: string;
  hint: string;
  rules: RuleDetail[];
  onSelect: (markId: string) => void;
}) {
  if (rules.length === 0) return null;
  return (
    <div>
      <h3 className="text-base font-semibold">{title}</h3>
      <p className="mb-3 text-sm text-muted">{hint}</p>
      <ul className="divide-y divide-line rounded-lg border border-line">
        {rules.map((r) => (
          <li key={r.rule_id} className="space-y-1.5 px-4 py-3">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <RuleStatusBadge status={r.status} />
              <span className="font-medium">{r.title}</span>
              <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">
                {r.rule_id}
              </span>
            </div>
            <p className="text-sm">{r.message}</p>
            {r.evidence_quote ? (
              <div className="flex flex-wrap items-start gap-2 text-sm text-muted">
                <q className="min-w-0 flex-1 break-words">{r.evidence_quote}</q>
                {r.span ? (
                  <button
                    type="button"
                    onClick={() => onSelect(ruleMarkId(r.rule_id))}
                    className="inline-flex items-center gap-1 text-xs text-accent underline-offset-2 hover:underline"
                  >
                    <MapPin size={14} aria-hidden="true" /> Show in text
                  </button>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-muted">No quote: the evidence is that it is not there.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function RuleChecklist({ rules, onSelect }: Props) {
  return (
    <div className="space-y-6">
      <Group
        title="Reject rules"
        hint="Any one that fails means the quote is rejected."
        rules={rules.filter((r) => r.rule_id.startsWith("R"))}
        onSelect={onSelect}
      />
      <Group
        title="Needs-a-person rules"
        hint="If none is rejected, any of these failing or unknown means a person must look."
        rules={rules.filter((r) => r.rule_id.startsWith("H"))}
        onSelect={onSelect}
      />
    </div>
  );
}
