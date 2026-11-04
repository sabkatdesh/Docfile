from pathlib import Path

import pytest

from docgate.ingest.pdf import EmptyPdfError, PdfReadError, extract_text

SAMPLES = Path(__file__).parents[2] / "data" / "sample"
PACKS = sorted(SAMPLES.glob("supplier-pack-*.pdf"))

# Valid one-page PDF with no text content.
BLANK_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R/Size 4>>\n%%EOF\n"
)


def test_all_ten_sample_packs_are_present() -> None:
    assert len(PACKS) == 10


@pytest.mark.parametrize("pdf", PACKS, ids=lambda p: p.stem)
def test_sample_pack_yields_text(pdf: Path) -> None:
    text = extract_text(pdf)
    assert "Quotation" in text or "QUOTATION" in text.upper()
    assert len(text.strip()) > 200


def test_empty_pdf_fails_loudly(tmp_path: Path) -> None:
    p = tmp_path / "blank.pdf"
    p.write_bytes(BLANK_PDF)
    with pytest.raises(EmptyPdfError):
        extract_text(p)


def test_garbage_file_fails_loudly(tmp_path: Path) -> None:
    p = tmp_path / "junk.pdf"
    p.write_bytes(b"this is not a pdf")
    with pytest.raises(PdfReadError):
        extract_text(p)


def test_missing_file_fails_loudly(tmp_path: Path) -> None:
    with pytest.raises(PdfReadError):
        extract_text(tmp_path / "nope.pdf")
