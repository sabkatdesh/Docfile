import { Check, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { Link } from "react-router";
import { asProblem, problemMessage } from "../../api/problem";
import { useEval } from "../../api/queries";
import type { EvalView } from "../../api/types";
import { Alert, Card, ErrorState, PageTitle, Skeleton } from "../../components/ui/primitives";
import { VerdictBadge } from "../../components/ui/VerdictBadge";
import { packLabel } from "../../lib/verdict";
import { ConfusionMatrix } from "./ConfusionMatrix";

function Summary({ golden }: { golden: EvalView["golden"] }) {
  const unsafe = golden.unsafe.length;
  const safe = unsafe === 0;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card aria-labelledby="golden-heading">
        <h2
          id="golden-heading"
          className="text-sm font-semibold uppercase tracking-wide text-muted"
        >
          Matches the golden set
        </h2>
        <p className="tabular mt-2 text-3xl font-semibold">
          {golden.correct} of {golden.total}
        </p>
        <p className="mt-1 flex items-center gap-2 text-sm">
          {golden.passed ? (
            <>
              <Check size={16} className="text-approve-fg" aria-hidden="true" /> Every pack got the
              expected verdict.
            </>
          ) : (
            <>
              <X size={16} className="text-reject-fg" aria-hidden="true" /> Some packs differ from
              the expected verdict.
            </>
          )}
        </p>
      </Card>
      <Card aria-labelledby="unsafe-heading">
        <h2
          id="unsafe-heading"
          className="text-sm font-semibold uppercase tracking-wide text-muted"
        >
          Unsafe errors
        </h2>
        <p className="tabular mt-2 text-3xl font-semibold">{unsafe}</p>
        <p
          className={`mt-1 flex items-center gap-2 text-sm ${safe ? "" : "font-semibold text-reject-fg"}`}
        >
          {safe ? (
            <>
              <ShieldCheck size={16} className="text-approve-fg" aria-hidden="true" /> Nothing was
              approved that should not have been.
            </>
          ) : (
            <>
              <ShieldAlert size={16} aria-hidden="true" /> Approved when it should not have been:{" "}
              {golden.unsafe.join(", ")}
            </>
          )}
        </p>
      </Card>
    </div>
  );
}

function GoldenTable({ rows }: { rows: EvalView["golden"]["rows"] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-sm">
        <caption className="sr-only">
          Expected verdict against the system verdict for each pack
        </caption>
        <thead>
          <tr className="border-b border-line text-left text-muted">
            <th scope="col" className="py-2 pr-4 font-medium">
              Pack
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Expected
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              System decided
            </th>
            <th scope="col" className="py-2 pr-4 font-medium">
              Match
            </th>
            <th scope="col" className="py-2 font-medium">
              A person decided
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.pack_id} className="border-b border-line last:border-0">
              <th scope="row" className="py-3 pr-4 text-left font-medium">
                <Link
                  className="text-accent underline-offset-2 hover:underline"
                  to={`/packs/${r.pack_id}`}
                >
                  {packLabel(r.pack_id)}
                </Link>
              </th>
              <td className="py-3 pr-4">
                <VerdictBadge decision={r.expected} />
              </td>
              <td className="py-3 pr-4">
                <VerdictBadge decision={r.actual} />
              </td>
              <td className="py-3 pr-4">
                {r.match ? (
                  <span className="inline-flex items-center gap-1 text-approve-fg">
                    <Check size={16} aria-hidden="true" /> Match
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 font-semibold text-reject-fg">
                    <X size={16} aria-hidden="true" /> Different
                  </span>
                )}
              </td>
              <td className="py-3">
                {r.human_decision ? (
                  <VerdictBadge decision={r.human_decision} />
                ) : (
                  <span className="text-muted">None</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Mutations({ mutation }: { mutation: EvalView["mutation"] }) {
  if (!mutation.available) {
    return <Alert tone="info">{mutation.reason ?? "The mutation checks are not available."}</Alert>;
  }
  return (
    <div className="space-y-3">
      <p className="text-muted">
        Each case changes one thing in a good quote (a price, a date, a clause) and checks the
        verdict moves the right way.{" "}
        <span className="tabular font-semibold text-fg">
          {mutation.passed} of {mutation.total}
        </span>{" "}
        passed.
      </p>
      {mutation.groups.map((g) => (
        <details key={g.family} className="rounded-lg border border-line">
          <summary className="flex cursor-pointer flex-wrap items-center justify-between gap-2 px-4 py-3 font-medium">
            <span className="capitalize">{g.family.replaceAll("_", " ")}</span>
            <span className="tabular text-sm text-muted">
              {g.passed} of {g.total} passed
            </span>
          </summary>
          <ul className="divide-y divide-line border-t border-line">
            {g.cases.map((c) => (
              <li
                key={c.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-sm"
              >
                {c.ok ? (
                  <Check size={16} className="text-approve-fg" aria-label="Passed" />
                ) : (
                  <X size={16} className="text-reject-fg" aria-label="Failed" />
                )}
                <span className="min-w-0 flex-1 break-words font-mono text-xs">{c.id}</span>
                <span className="text-muted">
                  expected {c.expect}, got {c.actual}
                </span>
                <span className="text-xs text-muted">
                  {Object.entries(c.fired)
                    .map(([rule, status]) => `${rule} ${status}`)
                    .join(", ")}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </div>
  );
}

export function EvaluationPage() {
  const query = useEval();
  return (
    <div>
      <PageTitle title="Evaluation" />
      {query.isPending ? (
        <div className="space-y-4" aria-busy="true">
          <Skeleton className="h-28" />
          <Skeleton className="h-72" />
        </div>
      ) : query.isError ? (
        <ErrorState
          title="The evaluation could not be loaded"
          message={problemMessage(asProblem(query.error))}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <div className="space-y-8">
          <p className="text-muted">
            Scored from the recorded readings, so it is the same every time and needs no network.
          </p>
          <Summary golden={query.data.golden} />
          <Card aria-labelledby="table-heading">
            <h2 id="table-heading" className="mb-3 text-lg font-semibold">
              Expected against actual
            </h2>
            <GoldenTable rows={query.data.golden.rows} />
          </Card>
          <Card aria-labelledby="matrix-heading">
            <h2 id="matrix-heading" className="mb-3 text-lg font-semibold">
              Confusion matrix
            </h2>
            <ConfusionMatrix confusion={query.data.golden.confusion} />
          </Card>
          <Card aria-labelledby="mutation-heading">
            <h2 id="mutation-heading" className="mb-3 text-lg font-semibold">
              Stress tests
            </h2>
            <Mutations mutation={query.data.mutation} />
          </Card>
        </div>
      )}
    </div>
  );
}
