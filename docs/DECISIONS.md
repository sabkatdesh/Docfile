# Decisions

Judgment calls made while building. Newest last.

## M0

- **Project name is `docgate`.** The plan documents say `suppliercheck`/`supplier-checker`; the package, distribution and repo all use `docgate`.
- **Task runner is `tasks.py`, not `make`.** `make` is not available on the Windows dev machine. `tasks.py` is plain Python (`setup|check|demo|live|eval`), so it works anywhere Python does and CI uses the same entry point. A thin `Makefile` forwards to it, so `make check` still works where make exists. `demo`, `live` and `eval` are stubs that exit 1 until their milestones.
- **Minimal dependencies.** Only `pydantic` and `pdfplumber` at runtime, plus ruff, mypy, pytest and pytest-cov for development. LangGraph, FastAPI and boto3 arrive with the milestones that use them. All versions are pinned.
- **Validators raise `ValueError`.** Pydantic only wraps `ValueError` into `ValidationError`; a `TypeError` would escape as a raw crash.
- **`Field` invariant.** An `OK` field must have a value and a quote; any other status must have no value. This enforces "no verified quote, no value" in the type itself, so later code cannot build a half-trusted value.
- **Floats are rejected** in `Field` values, config thresholds and `to_money`. Money is `Decimal` only.
- **Config holds the thresholds as the rules state them.** H4 is stored as "above 30 days" and R5 as "above 45 days", matching the strict "more than" semantics in the spec.
- **Empty PDF text raises `EmptyPdfError`.** No OCR (out of scope), so a scanned PDF fails loudly instead of yielding an empty string that downstream code could mistake for "no problems".

## M1

- **Dependency direction.** `compare` imports only `domain`; `rules` imports `domain` and `compare`, so delta and arithmetic math is written once. CLAUDE.md's "rules imports only domain" is read as "no I/O, no workflow, no LLM".
- **Exact boundaries.** Threshold comparisons (`is_above`, `differs_by_more_than` in `domain/money.py`) cross-multiply instead of dividing, so exactly +3% is H1 and never tips into R1 through rounding. `pct_delta` is for display only.
- **R3 and R4 treat MISSING as FAIL.** Absence of a penalty clause or TIN/BIN is the Reject condition (packs 06, 08). UNVERIFIED and CONFLICT stay UNKNOWN. Every other rule treats any non-OK status as UNKNOWN. These can only push toward Reject or a person, never Approve.
- **Pack 10 price.** A VAT-inclusive price (`vat_shown_separately` is False) cannot be compared to the PR max, so R1 and H1 are UNKNOWN. R5 still makes it Reject.
- **Unit mismatch.** Quoted unit missing or different from the PR unit (case-insensitive) makes R1, H1 and H2 UNKNOWN.
- **Implausible values** (price or qty <= 0, advance outside 0-100, negative penalty, delivery <= 0) are UNKNOWN, not PASS.
- **Arithmetic tolerance.** `RuleConfig.arithmetic_tolerance` = 0.01 BDT absolute. H5 owns the VAT-rate check; H6 owns line total and grand total (pack 09: 50,000 x 6.40 = 320,000 vs quoted 322,000).
- **Engine safety.** An exception inside a rule becomes UNKNOWN. A missing or duplicated rule result counts as UNKNOWN for that id. Approve only when all 12 rules PASS (property-tested over 5,000 seeded combinations).
- **Weeks to days** is an extraction concern (M2); M1 fixtures give days directly (pack 09: 4 weeks = 28).
- **Fixtures** in `tests/fixtures/packs.py` are hand-written with verbatim quotes, and a test checks each quote against the PDF text. M2 owns real quote verification.

## M2

- **LLM provider is Groq, `openai/gpt-oss-120b` (free tier), not Bedrock.** The `LLMProvider` protocol is unchanged, so the provider is a config value (`DOCGATE_PROVIDER=replay|groq`). Client is the official `groq` SDK pinned to 1.7.0, with `max_retries=0` so our own `RetryingProvider` is the only retry policy (testable with a fake clock, honest request counts). Structured output uses `json_schema` with `strict: true`; `best_effort` and `json_object` are config fallbacks. Free-tier limits (30 req/min, 8K tokens/min, 1K req/day, 200K tokens/day) mean live recording is paced.
- **LLM wire values are strings exactly as printed; code parses them.** The model never converts or computes (weeks to days, number formats, VAT). Status is assigned by code, never reported by the model.
- **Total LLM failure gives UNVERIFIED, not MISSING.** M1 treats MISSING as FAIL for R3/R4, so MISSING-on-outage would turn an outage into Reject. UNVERIFIED escalates to a person instead.
- **Dual extraction is required for every field the regex supports.** Both readers must agree (after quote verification). One side unreadable gives UNVERIFIED, one side absent while the other found a value gives CONFLICT, both absent gives MISSING. A bad LLM quote is never rescued by the regex alone.
- **Regex is tri-state** (FOUND / ABSENT / UNREADABLE). ABSENT means the clause anchor is not in the text; UNREADABLE means anchor present but pattern failed or two different matches.
- **CONFLICT keeps both values in `issues`**, not in `Field` (M0 invariant: non-OK carries no value), so the reviewer in M4 can see both sides.
- **Recordings store the raw response string**, keyed by sha256 of (pdf text, prompt version, model id, schema version, request params). Parsing and quote verification re-run on replay. Failures are never recorded.
- **"No advance payment required" gives advance 0** (packs 02, 07): one whitelisted case where the value is not literally in the quote.
- **`extraction/replay.py` replaced by `extraction/factory.py`**; recording and replay live in `llm/replay_provider.py`. Extra modules `llm/retry.py` and `extraction/parsing.py` keep one responsibility per file.
- **Strict number parsing** in `extraction/parsing.py` (not `domain.money.parse_money`, which would read `1.200,00` as 1.20000).
- **Prompt is `extract-v3`.** v1 let the model return whole sentences as values (parsed as UNVERIFIED, never guessed); v2 fixed that by requiring only the figure; v3 stopped it returning null for pack 06's one-letter `item_code` (caught as a CONFLICT by reconcile). Each bump changes the recording key, so all 10 were re-recorded.
- **Recordings keep the raw response even if the model slipped on a field;** only packs whose extraction failed outright are discarded.

## M3

- **LangGraph 1.1.2 pinned** (the version already vetted on this machine; official `langchain-ai` package). The SQLite checkpointer package arrives with M4.
- **Graph is fixed and explicit.** `ingest` fans out to `extract_llm` and `extract_regex`, which join at `reconcile`, then `compare_pr -> apply_rules -> decide -> human_gate -> report`. `human_gate` is a no-op in M3 and runs for every pack; M4 swaps its body for `interrupt()` without touching edges. Dependencies (extractors, PR lines, config) are closed over in `build_graph(deps)`, not stored in state, so state stays serializable. A test round-trips the full state through `InMemorySaver` to de-risk M4.
- **Failure never crashes and never approves.** Every node is `guarded`: an exception becomes a `NodeError` and the graph routes to `escalate`, which builds a Needs-a-person verdict (`rules/engine.escalate`, next to `decide`). A failed extractor still yields a failure output, so `reconcile` marks fields UNVERIFIED. A test forces a failure in each node on an Approve pack and asserts the verdict is never Approve.
- **Operator errors stop the batch.** `LLMConfigError` (bad key, exhausted budget) is recorded as `kind="config"`; the single-pack graph still escalates, but `run_packs` raises `OperatorError` (CLI exit 2) so one misconfiguration is not silently reported as ten "needs a person" packs.
- **`eval` and `run` are replay-only unless `--provider groq` is passed**, whatever `.env` says. `python tasks.py live` is `run --provider groq`; it was not run in M3.
- **Golden data lives in `data/golden/expected.json`**, hand-copied from SPEC section 9, loaded by both `eval` and the tests (`tests/golden/expected.py` now reads it). Shipped code must not import from `tests/`. Verdict values are unchanged.
- **Eval scores the automatic `decision`, never `human_decision`**, so a later human resolution cannot mask a wrong verdict. Unsafe error = actual Approve where golden is not Approve. A skipped or extra pack is a mismatch. Conservative misses (Reject expected, person asked) are shown separately, not counted as unsafe.
- **Reason text is templated, not LLM-written** (`reporting/explain.py`). For a Reject the first failing R rule in the company's listed order (R1..R5) leads, which is not a severity ranking; then "Also rejected by", "Also flagged" (H fails) and "Could not be checked" (UNKNOWN). A FAIL with no quote (MISSING field: packs 06, 08) says "not found in the document".
- **Reports** are pure models rendered to `runs/<out>/pack-id.json|md`, `summary.json|md` and `eval.json`; no timestamps, so reruns are byte-identical. Deltas are shown to 2 decimals and tested against the rule messages. `NodeError` lives in `domain` so `reporting` does not import `workflow`.

## M4

- **New dependency: `langgraph-checkpoint-sqlite==3.1.3`** (official langchain-ai package, MIT; pulls `aiosqlite` and `sqlite-vec`, which are unused here). Pinned in `pyproject.toml` and `requirements.txt`. `sqlite-vec` has placeholder PyPI metadata ("TODO"); it is the real package by its upstream author and is required by the checkpointer.
- **Only a machine "Needs a person" ever reaches the gate.** Enforced by the graph (`decide -> human_gate | report`), not by a check inside the node. Approve and Reject are final and never paused. A pack escalated by a node failure is a machine Needs-person verdict, so it pauses too.
- **The machine verdict is never overwritten.** `Verdict.human_review` (decision, reason, reviewer, `reviewed_at`) sits beside `decision`; `Verdict.human_decision` is now a read-only property. The report shows both, and `eval` still scores the machine decision.
- **Human answer is Approve or Reject with a non-blank reason.** "Needs a person" is not a valid answer. Reviewer and timestamp are mandatory; the timestamp must carry a timezone.
- **Pause is `interrupt()` with a SQLite checkpointer; thread id = pack id.** `human_gate` is not wrapped in `guarded` because the interrupt is an exception that must reach LangGraph. The node does nothing before `interrupt()` since it re-runs from the top on resume. The payload (question, machine verdict, non-PASS rules with quotes, extraction issues with both reads, node errors) is stored in the checkpoint and read back after a restart.
- **`build_graph` defaults to an in-memory checkpointer** and `run_pack` defaults the thread id to the pack id, so tests and `eval` pause packs without touching disk. `eval` never uses the SQLite file.
- **`reviewed_at` comes from an injected clock** (`GraphReviewStore(clock=...)`), never from inside the graph.
- **Refused requests change nothing.** Unknown pack, already resolved (names the first reviewer; first decision kept), machine-final pack, blank reason and invalid decision all raise a `ReviewError` before the graph is resumed; the CLI prints the message and exits 2. The check-then-resume is not atomic, which is fine for one operator and is not claimed as multi-user safe.
- **`run` skips packs already on record** in the checkpoint database and says so, so re-running never silently restarts a paused or resolved pack. Delete the database to start over. Review commands on a missing database fail instead of creating an empty one.
- **Reports.** A paused pack gets a provisional report ("Awaiting a human decision"); `run` and `resolve` rewrite the reports and summary for every pack on record. Existing reporting tests now read reports through `report_of(state)` because paused packs have no final report yet.
- **Reviewer** defaults to the OS username (`getpass.getuser()`), override with `--reviewer`.
- **Process note.** There is no `m3-done` tag in the repo; only `m2-done` existed before this commit.
- **Checkpoint serializer allowlist.** `review/checkpoint.py` lists every type stored in `PackState` for the msgpack serializer. LangGraph 1.1.2 only warns about unlisted types but says it will block them later; a test reads a full pause/resume checkpoint and fails on any "unregistered type" log line, so a new state type cannot slip in unnoticed.
- **Tests never write the default database.** The CLI `run` tests pass `--db` in `tmp_path`; the default `runs/checkpoints.sqlite` is for real use only.
