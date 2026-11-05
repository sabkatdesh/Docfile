import { Link } from "react-router";
import type { PendingReviewItem, RuleStatus } from "../../api/types";
import { Alert, Card } from "../../components/ui/primitives";
import { RuleStatusBadge } from "../../components/ui/RuleStatusBadge";
import { VerdictBadge } from "../../components/ui/VerdictBadge";
import { fieldLabel } from "../../lib/labels";
import { packLabel } from "../../lib/verdict";
import { ReviewForm } from "./ReviewForm";

/** The payload types the status as a plain string; anything unexpected is shown as Unknown,
 * never as a pass. */
function toRuleStatus(status: string): RuleStatus {
  return status === "PASS" || status === "FAIL" ? status : "UNKNOWN";
}

function Quote({
  label,
  value,
  quote,
}: {
  label: string;
  value: string | null;
  quote: string | null;
}) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-surface-2 p-3 text-sm">
      <p className="font-semibold">{label}</p>
      <p>{value ?? "Nothing found"}</p>
      {quote ? <q className="mt-1 block break-words text-muted">{quote}</q> : null}
    </div>
  );
}

export function ReviewCard({ item }: { item: PendingReviewItem }) {
  const { payload } = item;
  const headingId = `review-${item.pack_id}`;
  const open = payload.rules.filter((r) => r.status !== "PASS");

  return (
    <Card as="article" aria-labelledby={headingId} className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={headingId} className="text-lg font-semibold">
          {packLabel(item.pack_id)}
        </h2>
        <div className="flex items-center gap-3">
          <VerdictBadge decision={payload.machine_decision} />
          <Link
            to={`/packs/${item.pack_id}`}
            className="text-sm text-accent underline-offset-2 hover:underline"
          >
            See the full pack
          </Link>
        </div>
      </div>

      <p>{payload.question}</p>
      <p className="text-sm text-muted">{payload.reason}</p>

      {open.length > 0 ? (
        <div>
          <h3 className="mb-2 text-sm font-semibold">Rules that need a person</h3>
          <ul className="divide-y divide-line rounded-lg border border-line">
            {open.map((r) => (
              <li key={r.rule_id} className="space-y-1 px-4 py-3">
                <div className="flex flex-wrap items-center gap-3">
                  <RuleStatusBadge status={toRuleStatus(r.status)} />
                  <span className="font-medium">{r.title}</span>
                  <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">
                    {r.rule_id}
                  </span>
                </div>
                <p className="text-sm">{r.message}</p>
                {r.evidence_quote ? (
                  <q className="block break-words text-sm text-muted">{r.evidence_quote}</q>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {payload.issues.length > 0 ? (
        <div className="space-y-3">
          <h3 className="text-sm font-semibold">Where the two readers disagreed</h3>
          {payload.issues.map((issue) => (
            <div key={issue.field} className="space-y-2">
              <p className="text-sm">
                <span className="font-medium">{fieldLabel(issue.field)}:</span> {issue.reason}
              </p>
              <div className="grid gap-2 sm:grid-cols-2">
                <Quote label="First reader" value={issue.llm_value} quote={issue.llm_quote} />
                <Quote label="Second reader" value={issue.regex_value} quote={issue.regex_quote} />
              </div>
            </div>
          ))}
        </div>
      ) : null}

      {payload.errors.length > 0 ? (
        <Alert tone="error">
          <ul className="list-disc pl-5">
            {payload.errors.map((e) => (
              <li key={`${e.node}-${e.message}`}>
                {e.node}: {e.message}
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}

      <ReviewForm packId={item.pack_id} />
    </Card>
  );
}
