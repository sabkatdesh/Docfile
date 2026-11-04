"""Run both readers on one document and reconcile. The only place the two are combined."""

from __future__ import annotations

from docgate.extraction.base import Extractor
from docgate.extraction.reconcile import ReconcileResult, reconcile


def extract_document(text: str, label: str, llm: Extractor, regex: Extractor) -> ReconcileResult:
    return reconcile(llm.extract(text, label), regex.extract(text, label), text)
