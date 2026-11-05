import { UserCheck } from "lucide-react";
import { Link } from "react-router";
import type { PackDetail } from "../../api/types";
import { Alert, Card } from "../../components/ui/primitives";
import { VerdictBadge } from "../../components/ui/VerdictBadge";
import { formatDateTime, shortReason } from "../../lib/format";

export function VerdictCard({ detail }: { detail: PackDetail }) {
  const { machine, human_review: human } = detail;
  return (
    <Card aria-labelledby="verdict-heading" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2
          id="verdict-heading"
          className="text-sm font-semibold uppercase tracking-wide text-muted"
        >
          Verdict
        </h2>
        <VerdictBadge decision={human?.decision ?? machine.decision} size="lg" />
      </div>
      <p className="text-base">{shortReason(machine.headline)}</p>

      {human ? (
        <div className="space-y-1 rounded-lg border border-line bg-surface-2 p-4">
          <p className="flex items-center gap-2 font-semibold">
            <UserCheck size={18} aria-hidden="true" />A person decided: {human.decision}
          </p>
          <p className="text-sm">“{human.reason}”</p>
          <p className="text-sm text-muted">
            {human.reviewer}, {formatDateTime(human.reviewed_at)}
          </p>
          <p className="flex flex-wrap items-center gap-2 pt-1 text-sm text-muted">
            The automatic checks said: <VerdictBadge decision={machine.decision} />
          </p>
        </div>
      ) : detail.status === "pending_review" ? (
        <Alert tone="warning">
          Waiting for a person. Decide it in the{" "}
          <Link className="underline" to="/review">
            Review queue
          </Link>
          .
        </Alert>
      ) : null}

      {detail.errors.length > 0 ? (
        <Alert tone="error">
          <p className="font-semibold">Something failed while checking this pack:</p>
          <ul className="mt-1 list-disc pl-5">
            {detail.errors.map((e) => (
              <li key={`${e.node}-${e.message}`}>
                {e.node}: {e.message}
              </li>
            ))}
          </ul>
        </Alert>
      ) : null}
    </Card>
  );
}
