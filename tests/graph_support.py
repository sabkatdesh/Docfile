"""Shared wiring for graph tests: real replay extraction unless a test swaps one reader."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from docgate.domain.models import PRLine
from docgate.extraction.base import Extractor
from docgate.extraction.factory import build_llm_stack
from docgate.extraction.regex import RegexExtractor
from docgate.ingest.purchase_request import load_pr_lines
from docgate.settings import load_settings
from docgate.workflow.graph import Deps

ROOT = Path(__file__).parents[1]
SAMPLE = ROOT / "data" / "sample"
RECORDED = ROOT / "data" / "recorded"
PR_LINES = load_pr_lines(SAMPLE / "purchase-request.csv")


def pack_path(n: int) -> Path:
    return SAMPLE / f"supplier-pack-{n:02d}.pdf"


def replay_deps(
    *,
    llm: Extractor | None = None,
    regex: Extractor | None = None,
    pr_lines: Mapping[str, PRLine] | None = None,
) -> Deps:
    stack = build_llm_stack(load_settings({"DOCGATE_RECORDED_DIR": str(RECORDED)}))
    return Deps(
        llm=llm or stack.extractor,
        regex=regex or RegexExtractor(),
        pr_lines=PR_LINES if pr_lines is None else pr_lines,
    )


def base_texts_and_quotes() -> list[tuple[int, str, list[str]]]:
    """Each sample pack's ingest-normalised text with every quote its recording carries."""
    import json

    from docgate.ingest.pdf import extract_text
    from docgate.ingest.whitespace import normalise_whitespace

    out: list[tuple[int, str, list[str]]] = []
    for n in range(1, 11):
        path = next(RECORDED.glob(f"supplier-pack-{n:02d}__*.json"))
        response = json.loads(json.loads(path.read_text("utf-8"))["response"])
        quotes = [w["quote"] for w in response.values() if w.get("quote")]
        out.append((n, normalise_whitespace(extract_text(pack_path(n))), quotes))
    return out
