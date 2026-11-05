/** Plain-English names for the pipeline steps, for people who have never seen the graph. */
export const STEP_LABELS: Record<string, string> = {
  ingest: "Reading the PDF",
  extract_llm: "Extracting the fields",
  extract_regex: "Cross-checking with a second reader",
  reconcile: "Verifying every quote",
  compare_pr: "Comparing with the purchase request",
  apply_rules: "Checking the company rules",
  decide: "Reaching a verdict",
  human_gate: "Handing over to a person",
  report: "Writing the report",
  escalate: "Escalating to a person",
};

export function stepLabel(step: string): string {
  return STEP_LABELS[step] ?? step.replaceAll("_", " ");
}

/** The fixed order a pack passes through (the server also sends it with `pack_started`). */
export const DEFAULT_STEPS = [
  "ingest",
  "extract_llm",
  "extract_regex",
  "reconcile",
  "compare_pr",
  "apply_rules",
  "decide",
  "human_gate",
  "report",
] as const;
