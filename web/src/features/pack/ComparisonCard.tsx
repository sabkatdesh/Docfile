import { Check, MapPin, X } from "lucide-react";
import type { ComparisonDetail } from "../../api/types";
import { formatDelta, groupDigits } from "../../lib/format";
import { arithmeticLabel } from "../../lib/labels";
import { arithmeticMarkId } from "./marks";

const show = (v: string | null) => (v === null ? "–" : groupDigits(v));

function Row({
  label,
  requested,
  quoted,
  delta,
}: {
  label: string;
  requested: string | null;
  quoted: string | null;
  delta: string | null;
}) {
  return (
    <tr className="border-b border-line last:border-0">
      <th scope="row" className="py-3 pr-4 text-left font-medium">
        {label}
      </th>
      <td className="tabular py-3 pr-4 text-right">{show(requested)}</td>
      <td className="tabular py-3 pr-4 text-right">{show(quoted)}</td>
      <td className="tabular py-3 text-right font-semibold">{formatDelta(delta)}</td>
    </tr>
  );
}

interface Props {
  comparison: ComparisonDetail | null;
  onSelect: (markId: string) => void;
}

export function ComparisonCard({ comparison, onSelect }: Props) {
  if (comparison === null) {
    return (
      <p className="text-muted">
        There was nothing to compare: the quote could not be matched to the purchase request.
      </p>
    );
  }
  const c = comparison;
  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-1 text-base font-semibold">Quote against the purchase request</h3>
        {c.pr_line ? (
          <p className="mb-3 text-sm text-muted">
            {c.pr_line.pr_number}: {c.pr_line.description} (item {c.pr_line.item_code})
          </p>
        ) : null}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[28rem] text-sm">
            <caption className="sr-only">Requested against quoted, with the difference</caption>
            <thead>
              <tr className="border-b border-line text-muted">
                <th scope="col" className="py-2 pr-4 text-left font-medium">
                  What
                </th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">
                  Requested
                </th>
                <th scope="col" className="py-2 pr-4 text-right font-medium">
                  Quoted
                </th>
                <th scope="col" className="py-2 text-right font-medium">
                  Difference
                </th>
              </tr>
            </thead>
            <tbody>
              <Row
                label="Quantity"
                requested={c.requested_qty}
                quoted={c.quoted_qty}
                delta={c.qty_delta_pct}
              />
              <Row
                label="Unit price (BDT, requested is the maximum)"
                requested={c.max_unit_price}
                quoted={c.quoted_unit_price}
                delta={c.price_delta_pct}
              />
            </tbody>
          </table>
        </div>
        {c.price_note ? <p className="mt-2 text-sm text-muted">{c.price_note}</p> : null}
      </div>

      <div>
        <h3 className="mb-3 text-base font-semibold">Do the numbers add up?</h3>
        <ul className="divide-y divide-line rounded-lg border border-line">
          {c.arithmetic.map((a) => {
            const located = a.span !== null;
            return (
              <li
                key={a.check}
                className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{arithmeticLabel(a.check)}</p>
                  <p className="tabular text-sm text-muted">
                    Expected {show(a.expected)}, quote says {show(a.actual)}
                  </p>
                </div>
                {a.ok === null ? (
                  <span className="text-sm text-muted">Could not be checked</span>
                ) : a.ok ? (
                  <span className="inline-flex items-center gap-1 rounded-md border border-approve-line bg-approve-bg px-2 py-0.5 text-xs font-semibold text-approve-fg">
                    <Check size={14} aria-hidden="true" /> Matches
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-md border border-reject-line bg-reject-bg px-2 py-0.5 text-xs font-semibold text-reject-fg">
                    <X size={14} aria-hidden="true" /> Does not match
                  </span>
                )}
                {located ? (
                  <button
                    type="button"
                    onClick={() => onSelect(arithmeticMarkId(a.check))}
                    className="inline-flex items-center gap-1 text-xs text-accent underline-offset-2 hover:underline"
                  >
                    <MapPin size={14} aria-hidden="true" /> Show in text
                  </button>
                ) : null}
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}
