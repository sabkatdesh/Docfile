import { Check, X } from "lucide-react";
import { type FormEvent, useId, useRef, useState } from "react";
import { problemMessage } from "../../api/problem";
import { useResolveReview } from "../../api/queries";
import { Alert, Button } from "../../components/ui/primitives";
import { useToast } from "../../components/ui/Toast";
import { type ReviewDecision, type ReviewErrors, validateReview } from "../../lib/reviewForm";
import { packLabel } from "../../lib/verdict";

export function ReviewForm({ packId }: { packId: string }) {
  const resolve = useResolveReview();
  const toast = useToast();
  const base = useId();
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<ReviewErrors>({});
  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const groupRef = useRef<HTMLDivElement>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    const check = validateReview({ decision, reason });
    if (!check.ok) {
      setErrors(check.errors);
      // Send the reader to the first problem so a keyboard user is not left guessing.
      if (check.errors.decision) groupRef.current?.querySelector("button")?.focus();
      else reasonRef.current?.focus();
      return;
    }
    setErrors({});
    resolve.mutate(
      { packId, body: check.value },
      {
        onSuccess: () =>
          toast.success(
            `${packLabel(packId)} ${check.value.decision === "Approve" ? "approved" : "rejected"} by a person`,
          ),
      },
    );
  }

  const decisionError = errors.decision ? `${base}-decision-error` : undefined;
  const reasonError = errors.reason ? `${base}-reason-error` : undefined;

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <fieldset>
        <legend className="mb-2 text-sm font-semibold">Your decision</legend>
        <div
          ref={groupRef}
          role="radiogroup"
          aria-label="Your decision"
          aria-describedby={decisionError}
          className="flex flex-wrap gap-3"
        >
          {(["Approve", "Reject"] as const).map((value) => {
            const selected = decision === value;
            const Icon = value === "Approve" ? Check : X;
            const tone =
              value === "Approve"
                ? "border-approve-line bg-approve-bg text-approve-fg"
                : "border-reject-line bg-reject-bg text-reject-fg";
            return (
              // biome-ignore lint/a11y/useSemanticElements: styled toggle buttons in a radiogroup
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => {
                  setDecision(value);
                  setErrors((e) => ({ ...e, decision: undefined }));
                }}
                className={`inline-flex min-h-10 items-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold ${
                  selected
                    ? `${tone} ring-2 ring-accent-bg`
                    : "border-control bg-surface text-fg hover:bg-surface-2"
                }`}
              >
                <Icon size={16} aria-hidden="true" />
                {value}
              </button>
            );
          })}
        </div>
        {errors.decision ? (
          <p id={decisionError} className="mt-1 text-sm text-reject-fg">
            {errors.decision}
          </p>
        ) : null}
      </fieldset>

      <div>
        <label htmlFor={`${base}-reason`} className="mb-1 block text-sm font-semibold">
          Reason
        </label>
        <textarea
          id={`${base}-reason`}
          ref={reasonRef}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          aria-invalid={errors.reason ? true : undefined}
          aria-describedby={reasonError}
          className="w-full rounded-lg border border-control bg-surface p-3 text-sm"
        />
        {errors.reason ? (
          <p id={reasonError} className="mt-1 text-sm text-reject-fg">
            {errors.reason}
          </p>
        ) : null}
      </div>

      {resolve.isError ? <Alert tone="error">{problemMessage(resolve.error)}</Alert> : null}

      <Button type="submit" variant="primary" disabled={resolve.isPending}>
        {resolve.isPending ? "Saving…" : "Save decision"}
      </Button>
    </form>
  );
}
