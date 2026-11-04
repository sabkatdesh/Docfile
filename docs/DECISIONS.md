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
