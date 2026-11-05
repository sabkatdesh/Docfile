/** One shape for every failure the page can show: HTTP errors in the API's own
 * `{"error": {code, message, details}}` envelope, and a network failure that never got a response. */

export interface ApiProblem {
  /** HTTP status; 0 when no response arrived at all. */
  status: number;
  code: string;
  message: string;
  details: Record<string, unknown> | null;
}

export class ApiError extends Error {
  readonly problem: ApiProblem;
  constructor(problem: ApiProblem) {
    super(problem.message);
    this.name = "ApiError";
    this.problem = problem;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function problemFromBody(status: number, bodyText: string): ApiProblem {
  try {
    const body: unknown = JSON.parse(bodyText);
    const error = isRecord(body) ? body.error : undefined;
    if (isRecord(error) && typeof error.code === "string" && typeof error.message === "string") {
      return {
        status,
        code: error.code,
        message: error.message,
        details: isRecord(error.details) ? error.details : null,
      };
    }
  } catch {
    // not JSON (a proxy error page, say): fall through to the generic problem
  }
  return { status, code: "http_error", message: `The server answered ${status}.`, details: null };
}

export const networkProblem = (): ApiProblem => ({
  status: 0,
  code: "network",
  message: "Could not reach the server.",
  details: null,
});

export function asProblem(error: unknown): ApiProblem {
  if (error instanceof ApiError) return error.problem;
  return networkProblem();
}

/** Pack ids a fresh run would discard, when the problem is that 409; otherwise null. */
export function pendingPackIds(problem: ApiProblem): string[] | null {
  if (problem.code !== "pending_reviews_would_be_lost") return null;
  const ids = problem.details?.pack_ids;
  return Array.isArray(ids) ? ids.filter((x): x is string => typeof x === "string") : [];
}

function validationProblems(problem: ApiProblem): string[] {
  const list = problem.details?.problems;
  if (!Array.isArray(list)) return [];
  return list.flatMap((p) =>
    isRecord(p) && typeof p.problem === "string"
      ? [typeof p.where === "string" && p.where ? `${p.where}: ${p.problem}` : p.problem]
      : [],
  );
}

/** Words for a person, not a status code. The server's own message is the fallback. */
export function problemMessage(problem: ApiProblem): string {
  switch (problem.code) {
    case "network":
      return "Could not reach the server. Check that it is still running, then try again.";
    case "run_in_progress":
      return "A run is already in progress. Wait for it to finish, then try again.";
    case "already_resolved":
      return "Someone has already decided this pack, so it is no longer waiting.";
    case "machine_final":
      return "This pack was settled by the automatic checks and does not need a person.";
    case "unknown_pack":
    case "unknown_pack_number":
      return "That pack does not exist.";
    case "no_result":
      return "This pack has not been checked yet. Run the checks first.";
    case "pending_reviews_would_be_lost": {
      const n = pendingPackIds(problem)?.length ?? 0;
      return `Starting a new run would discard ${n} review${n === 1 ? "" : "s"} still waiting for a person.`;
    }
    case "invalid_review":
      return problem.message;
    case "validation_error": {
      const lines = validationProblems(problem);
      return lines.length > 0
        ? `The request was not accepted. ${lines.join("; ")}`
        : problem.message;
    }
    default:
      return problem.message;
  }
}
