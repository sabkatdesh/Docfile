import { Link } from "react-router";
import type { EvalView, PackListItem, PendingReviewItem } from "../../api/types";
import { Card, Skeleton } from "../../components/ui/primitives";

interface KpiProps {
  label: string;
  value: string;
  hint: string;
  tone?: "neutral" | "good" | "bad" | "attention";
  to?: string;
}

const TONE = {
  neutral: "",
  good: "text-approve-fg",
  bad: "text-reject-fg",
  attention: "text-review-fg",
} as const;

function Kpi({ label, value, hint, tone = "neutral", to }: KpiProps) {
  return (
    <Card as="div" className="flex flex-col gap-1">
      <p className="text-sm font-medium text-muted">{label}</p>
      <p className={`tabular text-3xl font-semibold tracking-tight ${TONE[tone]}`}>{value}</p>
      <p className="text-sm text-muted">
        {to ? (
          <Link to={to} className="text-accent underline underline-offset-2">
            {hint}
          </Link>
        ) : (
          hint
        )}
      </p>
    </Card>
  );
}

interface Props {
  packs: PackListItem[] | undefined;
  review: PendingReviewItem[] | undefined;
  evaluation: EvalView | undefined;
  loading: boolean;
}

export function KpiRow({ packs, review, evaluation, loading }: Props) {
  if (loading) {
    return (
      <div
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"
        role="status"
        aria-label="Loading summary"
      >
        {[0, 1, 2, 3].map((i) => (
          <Card key={i} as="div" className="space-y-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-4 w-32" />
          </Card>
        ))}
      </div>
    );
  }
  const total = packs?.length ?? 0;
  const checked = packs?.filter((p) => p.status !== "not_run").length ?? 0;
  const started = checked > 0;
  const golden = evaluation?.golden;
  const unsafe = golden?.unsafe.length ?? 0;
  const waiting = review?.length ?? 0;
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi
        label="Packs checked"
        value={`${checked} of ${total}`}
        hint={started ? "Quotation packs read and judged" : "Run the checks to begin"}
      />
      <Kpi
        label="Accuracy vs golden answers"
        value={started && golden ? `${golden.correct} of ${golden.total}` : "–"}
        hint={started ? "Scored from the recorded readings" : "Appears after the first run"}
        tone={started && golden ? (golden.passed ? "good" : "bad") : "neutral"}
      />
      <Kpi
        label="Unsafe errors"
        value={started && golden ? String(unsafe) : "–"}
        hint={
          started
            ? unsafe === 0
              ? "No pack was approved that should not be"
              : "A pack was approved that should not be"
            : "A wrong Approve is the worst error"
        }
        tone={started ? (unsafe === 0 ? "good" : "bad") : "neutral"}
      />
      <Kpi
        label="Awaiting a person"
        value={String(waiting)}
        hint={waiting > 0 ? "Open the review queue" : "Nothing is waiting"}
        tone={waiting > 0 ? "attention" : "neutral"}
        to={waiting > 0 ? "/review" : undefined}
      />
    </div>
  );
}
