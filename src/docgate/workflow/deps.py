"""What the graph needs from the outside world, passed in rather than reached for."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from docgate.domain.config import DEFAULT_CONFIG, RuleConfig
from docgate.domain.models import PRLine
from docgate.extraction.base import Extractor
from docgate.ingest.pdf import extract_text


@dataclass(frozen=True)
class Deps:
    llm: Extractor
    regex: Extractor
    pr_lines: Mapping[str, PRLine]
    config: RuleConfig = DEFAULT_CONFIG
    read_text: Callable[[Path], str] = extract_text
