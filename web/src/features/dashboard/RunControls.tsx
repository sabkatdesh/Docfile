import { Play } from "lucide-react";
import { useState } from "react";
import { asProblem, pendingPackIds, problemMessage } from "../../api/problem";
import type { RunRequest } from "../../api/types";
import { Button } from "../../components/ui/primitives";
import { useToast } from "../../components/ui/Toast";
import { useRun } from "../../state/RunProvider";
import { DiscardDialog } from "./DiscardDialog";

const RUN_ALL: RunRequest = { packs: null, resume: false, discard_pending: false };

export function RunControls({ hasResults }: { hasResults: boolean }) {
  const run = useRun();
  const toast = useToast();
  const [discard, setDiscard] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  async function begin(body: RunRequest) {
    setBusy(true);
    try {
      await run.start(body);
      setDiscard(null);
    } catch (error) {
      const problem = asProblem(error);
      const waiting = pendingPackIds(problem);
      if (waiting !== null) {
        setDiscard(waiting); // ask first; never discard silently
      } else {
        setDiscard(null);
        toast.error(problemMessage(problem));
      }
    } finally {
      setBusy(false);
    }
  }

  const running = run.active;
  return (
    <>
      <Button
        variant="primary"
        icon={<Play size={16} aria-hidden="true" />}
        disabled={running || busy}
        onClick={() => void begin(RUN_ALL)}
      >
        {running
          ? `Checking… ${run.state.settled} of ${run.state.total}`
          : hasResults
            ? "Run all again"
            : "Run all checks"}
      </Button>
      <DiscardDialog
        packIds={discard}
        busy={busy}
        onCancel={() => setDiscard(null)}
        onConfirm={() => void begin({ ...RUN_ALL, discard_pending: true })}
      />
    </>
  );
}
