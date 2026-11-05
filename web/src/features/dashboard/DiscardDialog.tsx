import { Dialog } from "../../components/ui/Dialog";
import { Button } from "../../components/ui/primitives";
import { packLabel } from "../../lib/verdict";

interface Props {
  /** Pack ids whose waiting reviews a fresh run would throw away. Null keeps the dialog closed. */
  packIds: string[] | null;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DiscardDialog({ packIds, busy = false, onCancel, onConfirm }: Props) {
  const ids = packIds ?? [];
  const n = ids.length;
  return (
    <Dialog open={packIds !== null} title="Discard waiting reviews?" onClose={onCancel}>
      <p className="text-fg">
        Starting a new run will{" "}
        <strong>
          discard {n} review{n === 1 ? "" : "s"}
        </strong>{" "}
        that {n === 1 ? "is" : "are"} still waiting for a person:
      </p>
      <ul className="my-3 list-disc pl-6 text-fg">
        {ids.map((id) => (
          <li key={id}>{packLabel(id)}</li>
        ))}
      </ul>
      <p className="text-sm text-muted">
        Nothing has been decided for {n === 1 ? "it" : "them"} yet. This cannot be undone. To keep{" "}
        {n === 1 ? "it" : "them"}, cancel and resolve {n === 1 ? "it" : "them"} in the Review queue
        first.
      </p>
      <div className="mt-6 flex flex-wrap justify-end gap-3">
        {/* Cancel first in the DOM so it is the default focus: the safe choice. */}
        <Button onClick={onCancel} autoFocus>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} disabled={busy}>
          Discard and run
        </Button>
      </div>
    </Dialog>
  );
}
