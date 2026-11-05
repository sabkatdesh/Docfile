import { WifiOff } from "lucide-react";
import { asProblem, problemMessage } from "../../api/problem";
import { useEval, usePacks, useReview } from "../../api/queries";
import {
  Alert,
  Card,
  EmptyState,
  ErrorState,
  PageTitle,
  Skeleton,
} from "../../components/ui/primitives";
import { useRun } from "../../state/RunProvider";
import { KpiRow } from "./KpiRow";
import { PackTable } from "./PackTable";
import { RunControls } from "./RunControls";

function RunBanner() {
  const { state } = useRun();
  if (state.connection === "reconnecting") {
    return (
      <Alert tone="warning">
        <span className="inline-flex items-center gap-2">
          <WifiOff size={16} aria-hidden="true" /> Connection lost, reconnecting… Progress shown may
          be a few steps behind.
        </span>
      </Alert>
    );
  }
  if (state.connection === "lost" && state.status === "running") {
    return (
      <Alert tone="warning">
        <span className="inline-flex items-center gap-2">
          <WifiOff size={16} aria-hidden="true" /> Live updates stopped. Checking the server every
          couple of seconds instead.
        </span>
      </Alert>
    );
  }
  if (state.status === "lost") {
    return (
      <Alert tone="info">
        The run finished while this page was disconnected. The results below are up to date, but the
        step-by-step progress was missed.
      </Alert>
    );
  }
  if (state.status === "failed") {
    return (
      <Alert tone="error">
        The run stopped: {state.error ?? "an unexpected problem occurred"}. Packs already checked
        keep their verdicts.
      </Alert>
    );
  }
  if (state.status === "finished") {
    const parts = Object.entries(state.counts).map(([d, n]) => `${n} ${d}`);
    return <Alert tone="info">Run complete{parts.length ? `: ${parts.join(", ")}` : ""}.</Alert>;
  }
  return null;
}

function OverallProgress() {
  const { state } = useRun();
  if (state.status !== "running" || state.total === 0) return null;
  return (
    <div className="space-y-2">
      <p aria-live="polite" className="text-sm font-medium">
        {state.settled} of {state.total} packs done
      </p>
      <div
        role="progressbar"
        aria-label="Packs checked"
        aria-valuemin={0}
        aria-valuemax={state.total}
        aria-valuenow={state.settled}
        className="h-2 overflow-hidden rounded-full bg-surface-2"
      >
        <div
          className="h-full rounded-full bg-accent-bg transition-[width]"
          style={{ width: `${(state.settled / state.total) * 100}%` }}
        />
      </div>
    </div>
  );
}

export function DashboardPage() {
  const packs = usePacks();
  const review = useReview();
  const evaluation = useEval();
  const { state } = useRun();

  const loading = packs.isPending;
  const ranAny = packs.data?.some((p) => p.status !== "not_run") ?? false;

  return (
    <div className="space-y-6">
      <PageTitle title="Dashboard">
        <RunControls hasResults={ranAny} />
      </PageTitle>
      <p className="-mt-3 max-w-2xl text-muted">
        Ten supplier quotes, checked against the purchase request and the company rules. Each gets
        one of three answers, with the evidence behind it.
      </p>

      <RunBanner />
      <OverallProgress />

      <KpiRow
        packs={packs.data}
        review={review.data}
        evaluation={evaluation.data}
        loading={loading}
      />

      <Card className="p-0">
        {packs.isPending ? (
          <div className="space-y-3 p-5" role="status" aria-label="Loading packs">
            {["a", "b", "c", "d", "e", "f"].map((k) => (
              <Skeleton key={k} className="h-10 w-full" />
            ))}
          </div>
        ) : packs.isError ? (
          <ErrorState
            title="Could not load the packs"
            message={problemMessage(asProblem(packs.error))}
            onRetry={() => void packs.refetch()}
          />
        ) : !ranAny && state.status !== "running" ? (
          <EmptyState title="No packs checked yet">
            Press “Run all checks” above to read all {packs.data.length} supplier quotes and get a
            verdict for each. It takes a few seconds.
          </EmptyState>
        ) : (
          <PackTable packs={packs.data} progress={state.packs} />
        )}
      </Card>
    </div>
  );
}
