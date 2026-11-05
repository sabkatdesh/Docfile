import type { Decision } from "../api/types";

export type ReviewDecision = Extract<Decision, "Approve" | "Reject">;

export interface ReviewInput {
  decision: ReviewDecision | null;
  reason: string;
}

export interface ReviewErrors {
  decision?: string;
  reason?: string;
}

export type ReviewCheck =
  | { ok: true; value: { decision: ReviewDecision; reason: string } }
  | { ok: false; errors: ReviewErrors };

/** The server stays the authority; this only stops an obviously empty submission early. */
export function validateReview(input: ReviewInput): ReviewCheck {
  const errors: ReviewErrors = {};
  const reason = input.reason.trim();
  if (input.decision === null) errors.decision = "Choose Approve or Reject.";
  if (reason === "") errors.reason = "Write a reason. It is saved in the audit record.";
  if (errors.decision || errors.reason || input.decision === null) return { ok: false, errors };
  return { ok: true, value: { decision: input.decision, reason } };
}
