import { Check, CircleHelp, MapPin, TriangleAlert } from "lucide-react";
import type { FieldDetail } from "../../api/types";
import { fieldLabel, fieldStatusLabel, fieldValue } from "../../lib/labels";
import { fieldMarkId } from "./marks";

function StatusChip({ status }: { status: string }) {
  const ok = status === "OK";
  const Icon = ok ? Check : status === "MISSING" ? CircleHelp : TriangleAlert;
  const cls = ok
    ? "bg-approve-bg text-approve-fg border-approve-line"
    : "bg-review-bg text-review-fg border-review-line";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold ${cls}`}
    >
      <Icon size={14} aria-hidden="true" />
      {fieldStatusLabel(status)}
    </span>
  );
}

interface Props {
  fields: FieldDetail[];
  activeId: string | null;
  onSelect: (markId: string) => void;
}

export function FieldList({ fields, activeId, onSelect }: Props) {
  return (
    <div>
      <p className="mb-3 text-sm text-muted">
        Select a field to jump to the exact words it was read from.
      </p>
      <ul className="divide-y divide-line rounded-lg border border-line">
        {fields.map((f) => {
          const id = fieldMarkId(f.name);
          const located = f.span !== null;
          const selected = activeId === id;
          return (
            <li key={f.name}>
              <button
                type="button"
                disabled={!located}
                aria-pressed={selected}
                onClick={() => onSelect(id)}
                className={`flex w-full flex-col gap-1 px-4 py-3 text-left enabled:hover:bg-surface-2 sm:flex-row sm:items-center sm:gap-4 ${
                  selected ? "bg-surface-2" : ""
                }`}
              >
                <span className="w-full text-sm text-muted sm:w-48 sm:shrink-0">
                  {fieldLabel(f.name)}
                </span>
                <span className="tabular min-w-0 flex-1 break-words font-medium">
                  {fieldValue(f.name, f.value)}
                </span>
                <span className="flex items-center gap-2">
                  <StatusChip status={f.status} />
                  {located ? (
                    <span className="inline-flex items-center gap-1 text-xs text-accent">
                      <MapPin size={14} aria-hidden="true" />
                      Show in text
                    </span>
                  ) : null}
                </span>
              </button>
              {!located ? (
                <p className="px-4 pb-3 text-sm text-muted">
                  {f.issue ??
                    (f.quote
                      ? "The quote could not be placed in the text, so nothing is highlighted."
                      : "No verified quote, so no value is used.")}
                </p>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
