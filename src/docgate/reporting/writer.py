"""The only place reports touch the disk."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from docgate.reporting.report import (
    PackReport,
    build_summary,
    render_json,
    render_markdown,
    render_summary_markdown,
)


def _write(path: Path, text: str) -> None:
    # newline="" keeps bytes identical across platforms, so reruns diff clean.
    with path.open("w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def write_pack(report: PackReport, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for suffix, text in ((".json", render_json(report)), (".md", render_markdown(report))):
        path = out_dir / f"{report.pack_id}{suffix}"
        _write(path, text)
        written.append(path)
    return written


def write_run(reports: Sequence[PackReport], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for r in reports:
        written += write_pack(r, out_dir)
    summary = build_summary(reports)
    for name, text in (
        ("summary.json", render_json(summary)),
        ("summary.md", render_summary_markdown(summary)),
    ):
        _write(out_dir / name, text)
        written.append(out_dir / name)
    return written
