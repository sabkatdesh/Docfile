import type { GoldenView } from "../../api/types";

const SHORT: Record<string, string> = {
  Approve: "Approve",
  Reject: "Reject",
  "Needs a person to check": "Needs a person",
};

/** Rows are what the golden set expects, columns are what the system decided. The diagonal is
 * emphasised by weight and a border, not only by colour. */
export function ConfusionMatrix({ confusion }: { confusion: GoldenView["confusion"] }) {
  const { labels, counts } = confusion;
  return (
    <div className="overflow-x-auto">
      <table className="min-w-[28rem] border-separate border-spacing-1 text-sm">
        <caption className="mb-2 text-left text-muted">
          How often each expected verdict (rows) became each system verdict (columns). Counts on the
          diagonal are correct.
        </caption>
        <thead>
          <tr>
            <td />
            <th
              scope="colgroup"
              colSpan={labels.length}
              className="pb-1 text-center font-medium text-muted"
            >
              System decided
            </th>
          </tr>
          <tr>
            <th scope="col" className="text-left font-medium text-muted">
              Expected
            </th>
            {labels.map((l) => (
              <th key={l} scope="col" className="px-2 text-center font-medium">
                {SHORT[l] ?? l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((row, i) => (
            <tr key={row}>
              <th scope="row" className="pr-3 text-left font-medium">
                {SHORT[row] ?? row}
              </th>
              {labels.map((col, j) => {
                const n = counts[i]?.[j] ?? 0;
                const diagonal = i === j;
                return (
                  <td
                    key={col}
                    className={`tabular h-12 min-w-20 rounded-md border text-center ${
                      diagonal
                        ? "border-fg bg-surface-2 text-base font-bold"
                        : n > 0
                          ? "border-reject-line bg-reject-bg font-semibold text-reject-fg"
                          : "border-line text-muted"
                    }`}
                  >
                    {n}
                    <span className="sr-only">
                      {" "}
                      expected {row}, system decided {col}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
