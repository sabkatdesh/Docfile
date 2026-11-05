import type { Decision, RuleStatus } from "../api/types";

export type Tone = "approve" | "reject" | "review";

/** Wording is fixed by the brief and equals the API's `Decision` values. */
export const DECISION_TONE: Record<Decision, Tone> = {
  Approve: "approve",
  Reject: "reject",
  "Needs a person to check": "review",
};

export const RULE_STATUS_LABEL: Record<RuleStatus, string> = {
  PASS: "Pass",
  FAIL: "Fail",
  UNKNOWN: "Unknown",
};

/** "supplier-pack-04" -> "04". Falls back to the id when it has no trailing number. */
export function packNumber(packId: string): string {
  return /(\d+)$/.exec(packId)?.[1] ?? packId;
}

export function packLabel(packId: string): string {
  return `Pack ${packNumber(packId)}`;
}
