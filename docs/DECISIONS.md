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
