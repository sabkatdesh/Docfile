import { Link } from "react-router";
import type { PackListItem } from "../../api/types";
import { VerdictBadge } from "../../components/ui/VerdictBadge";
import { shortReason } from "../../lib/format";
import type { PackProgress } from "../../lib/runReducer";
import { DEFAULT_STEPS, stepLabel } from "../../lib/steps";
import { packLabel } from "../../lib/verdict";

function MiniProgress({ progress }: { progress: PackProgress }) {
  const steps = progress.steps.length > 0 ? progress.steps : [...DEFAULT_STEPS];
  const doneCount = progress.done.length;
  return (
    <div className="min-w-48">
      <div
        role="progressbar"
        aria-label="Steps completed"
        aria-valuemin={0}
        aria-valuemax={steps.length}
        aria-valuenow={doneCount}
        className="flex gap-0.5"
      >
        {steps.map((s, i) => (
          <span
            key={s}
            className={`h-1.5 flex-1 rounded-full ${i < doneCount ? "bg-accent-bg" : "bg-surface-2"}`}
          />
        ))}
      </div>
      <p className="mt-1.5 text-sm text-muted">
        {progress.current ? `${stepLabel(progress.current)}…` : "Finishing…"}
      </p>
    </div>
  );
}

function VerdictCell({ item, progress }: { item: PackListItem; progress?: PackProgress }) {
  if (progress?.phase === "running") return <MiniProgress progress={progress} />;
  if (progress?.phase === "queued")
    return <span className="text-sm text-muted">Waiting in line…</span>;
  return (
    <div className="flex flex-col items-start gap-1">
      <VerdictBadge decision={item.decision} />
      {item.status === "pending_review" ? (
        <span className="text-xs text-muted">Waiting for a person</span>
      ) : null}
      {item.status === "resolved" && item.human_decision ? (
        <span className="text-xs text-muted">Person decided: {item.human_decision}</span>
      ) : null}
    </div>
  );
}

interface Props {
  packs: PackListItem[];
  progress: Record<string, PackProgress>;
}

export function PackTable({ packs, progress }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[44rem] border-collapse text-left">
        <caption className="sr-only">The ten supplier quotation packs and their verdicts</caption>
        <thead>
          <tr className="border-b border-line text-sm text-muted">
            <th scope="col" className="px-4 py-3 font-medium">
              Pack
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Supplier
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Item
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Verdict
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Main reason
            </th>
          </tr>
        </thead>
        <tbody>
          {packs.map((p) => {
            const live = progress[p.pack_id];
            const ran = p.status !== "not_run";
            return (
              <tr
                key={p.pack_id}
                className="border-b border-line last:border-0 hover:bg-surface-2/60"
              >
                <td className="px-4 py-3.5 align-top font-medium">
                  <Link
                    to={`/packs/${p.pack_id}`}
                    className="text-accent underline-offset-2 hover:underline"
                  >
                    {packLabel(p.pack_id)}
                    <span className="sr-only">: open details</span>
                  </Link>
                </td>
                <td className="px-4 py-3.5 align-top">
                  {p.supplier ?? <span className="text-muted">–</span>}
                </td>
                <td className="tabular px-4 py-3.5 align-top">
                  {p.item ?? <span className="text-muted">–</span>}
                </td>
                <td className="px-4 py-3.5 align-top">
                  <VerdictCell item={p} progress={live} />
                </td>
                <td className="max-w-md px-4 py-3.5 align-top text-sm">
                  {ran ? (
                    shortReason(p.headline)
                  ) : (
                    <span className="text-muted">Not checked yet</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
