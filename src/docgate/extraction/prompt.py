"""Prompts live in versioned files, never inline, so a change is visible in review and in keys."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

PROMPT_VERSION = "extract-v3"


@dataclass(frozen=True)
class Prompt:
    version: str
    text: str


def load_prompt(version: str = PROMPT_VERSION) -> Prompt:
    name = version.replace("-", "_") + ".md"
    text = resources.files("docgate.extraction").joinpath("prompts", name).read_text("utf-8")
    return Prompt(version=version, text=text)
