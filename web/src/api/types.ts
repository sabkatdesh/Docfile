import type { components } from "./schema";

type S = components["schemas"];

export type Decision = S["Decision"];
export type RuleStatus = S["RuleStatus"];
export type PackListItem = S["PackListItem"];
export type PackDetail = S["PackDetail"];
export type PackStatus = PackListItem["status"];
export type FieldDetail = S["FieldDetail"];
export type RuleDetail = S["RuleDetail"];
export type ArithmeticDetail = S["ArithmeticDetail"];
export type ComparisonDetail = S["ComparisonDetail"];
export type MachineVerdict = S["MachineVerdict"];
export type HumanReview = S["HumanReview"];
export type TextSpan = S["TextSpan"];
export type PendingReviewItem = S["PendingReviewItem"];
export type ReviewPayload = S["ReviewPayload"];
export type PayloadRule = S["PayloadRule"];
export type PayloadIssue = S["PayloadIssue"];
export type NodeError = S["NodeError"];
export type EvalView = S["EvalView"];
export type GoldenView = S["GoldenView"];
export type EvalRowView = S["EvalRowView"];
export type MutationView = S["MutationView"];
export type MutationGroup = S["MutationGroup"];
export type MutationCase = S["MutationCase"];
export type Health = S["Health"];
export type RunRequest = S["RunRequest"];
export type RunAccepted = S["RunAccepted"];
export type ReviewRequest = S["ReviewRequest"];

export const DECISIONS: readonly Decision[] = ["Approve", "Reject", "Needs a person to check"];
