"""PDF to text. Text PDFs only (no OCR); empty output is an error, never a silent empty string."""

from __future__ import annotations

from pathlib import Path

import pdfplumber


class PdfReadError(Exception):
    """The file is missing, corrupt or not a PDF."""


class EmptyPdfError(PdfReadError):
    """The PDF opened but holds no extractable text (likely scanned)."""


def extract_text(path: Path) -> str:
    try:
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
    except Exception as exc:  # pdfplumber/pdfminer raise many unrelated types on bad input
        raise PdfReadError(f"cannot read {path}: {exc}") from exc
    text = "\n".join(pages).strip()
    if not text:
        raise EmptyPdfError(f"{path} has no extractable text; scanned PDFs need OCR (unsupported)")
    return text
