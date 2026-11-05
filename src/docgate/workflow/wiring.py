"""Build the graph's dependencies from settings. Shared by the CLI and the API, so both read
packs the same way and switching provider is configuration only."""

from __future__ import annotations

from pathlib import Path

from docgate.extraction.factory import build_llm_stack
from docgate.extraction.regex import RegexExtractor
from docgate.ingest.purchase_request import load_pr_lines
from docgate.settings import Settings
from docgate.workflow.deps import Deps


def build_deps(settings: Settings, sample_dir: Path) -> Deps:
    return Deps(
        llm=build_llm_stack(settings).extractor,
        regex=RegexExtractor(),
        pr_lines=load_pr_lines(sample_dir / "purchase-request.csv"),
    )
