"""Thin command-line shell: `extract` prints what was read, `record` captures live responses."""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from docgate.domain.models import Extraction, FieldStatus
from docgate.extraction.factory import build_llm_stack
from docgate.extraction.quotes import verify_quote
from docgate.extraction.regex import RegexExtractor
from docgate.extraction.service import extract_document
from docgate.ingest.pdf import extract_text
from docgate.llm.provider import LLMConfigError
from docgate.settings import Settings, SettingsError, load_settings, parse_env_file

SAMPLE_DIR = Path("data/sample")
SMOKE_PACK = 4  # a pack with every field present, so one request exercises the whole schema


def _environment(env_file: Path = Path(".env")) -> Mapping[str, str]:
    values = parse_env_file(env_file.read_text("utf-8")) if env_file.is_file() else {}
    return {**values, **os.environ}  # real environment variables win over .env


def _packs(numbers: Sequence[int] | None) -> list[Path]:
    paths = sorted(SAMPLE_DIR.glob("supplier-pack-*.pdf"))
    if numbers:
        wanted = {f"supplier-pack-{n:02d}" for n in numbers}
        paths = [p for p in paths if p.stem in wanted]
    if not paths:
        raise SettingsError(f"no matching supplier packs in {SAMPLE_DIR}")
    return paths


def cmd_extract(settings: Settings, packs: list[Path]) -> int:
    stack = build_llm_stack(settings)
    regex = RegexExtractor()
    totals: Counter[str] = Counter()
    ok_quotes = ok_fields = 0
    print(f"provider={settings.provider} model={settings.groq_model}")
    print(
        f"{'pack':<20} {'OK':>3} {'MISSING':>8} {'UNVERIFIED':>11} {'CONFLICT':>9}  verified quotes"
    )
    for path in packs:
        text = extract_text(path)
        result = extract_document(text, path.stem, stack.extractor, regex)
        counts: Counter[str] = Counter()
        verified = ok = 0
        for name in Extraction.model_fields:
            f: Any = getattr(result.extraction, name)
            counts[f.status.value] += 1
            if f.status is FieldStatus.OK:
                ok += 1
                verified += verify_quote(f.quote, text)
        totals.update(counts)
        ok_fields += ok
        ok_quotes += verified
        print(
            f"{path.stem:<20} {counts['OK']:>3} {counts['MISSING']:>8} "
            f"{counts['UNVERIFIED']:>11} {counts['CONFLICT']:>9}  {verified}/{ok}"
        )
        for issue in result.issues:
            print(f"    {issue.status.value:<10} {issue.field}: {issue.reason}")
    print(
        f"TOTAL: {totals['OK']} OK, {totals['MISSING']} MISSING, "
        f"{totals['UNVERIFIED']} UNVERIFIED, {totals['CONFLICT']} CONFLICT; "
        f"verified quotes: {ok_quotes}/{ok_fields}"
    )
    return 0


def cmd_record(settings: Settings, packs: list[Path], force: bool) -> int:
    stack = build_llm_stack(settings, record=True, overwrite=force)
    assert stack.recorder is not None and stack.live is not None
    failures = 0
    for path in packs:
        out = stack.extractor.extract(extract_text(path), path.stem)
        if out.failure:
            stack.recorder.discard_written()  # failed extractions are never recorded
            failures += 1
            print(f"FAILED   {path.stem}: {out.failure}")
        else:
            print(f"recorded {path.stem}")
    print(f"requests sent: {stack.live.requests_made}; failed packs: {failures}")
    print("next: python tasks.py extract")
    return 1 if failures else 0


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="docgate")
    sub = parser.add_subparsers(dest="command", required=True)
    ex = sub.add_parser("extract", help="read all sample packs with the configured provider")
    ex.add_argument("--pack", type=int, action="append", help="pack number, repeatable")
    rec = sub.add_parser(
        "record", help="call Groq and record the raw responses (live, costs requests)"
    )
    rec.add_argument("--pack", type=int, action="append", help="pack number, repeatable")
    rec.add_argument("--smoke", action="store_true", help=f"one request, pack {SMOKE_PACK} only")
    rec.add_argument("--force", action="store_true", help="overwrite existing recordings")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(_environment())
        if args.command == "extract":
            return cmd_extract(settings, _packs(args.pack))
        return cmd_record(settings, _packs([SMOKE_PACK] if args.smoke else args.pack), args.force)
    except (SettingsError, LLMConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
