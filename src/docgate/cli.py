"""Thin command-line shell: `extract` reads, `record` captures live responses, `run` writes
reports and `eval` scores the golden set. Logic lives in the packages; this only wires them."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sqlite3
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from docgate.api.serve import OPENAPI_FILE, ServeOptions, build_app, is_loopback, openapi_text
from docgate.domain.models import Decision, Extraction, FieldStatus
from docgate.evaluation.golden import GoldenError, load_golden
from docgate.evaluation.score import render_report, result_to_dict, score
from docgate.extraction.factory import build_llm_stack
from docgate.extraction.quotes import verify_quote
from docgate.extraction.regex import RegexExtractor
from docgate.extraction.service import extract_document
from docgate.ingest.pdf import extract_text
from docgate.ingest.purchase_request import PurchaseRequestError
from docgate.llm.provider import LLMConfigError
from docgate.reporting.writer import write_run
from docgate.review.checkpoint import DEFAULT_DB, sqlite_saver
from docgate.review.fresh import discard, start_fresh
from docgate.review.render import render_pending, render_status
from docgate.review.service import GraphReviewStore
from docgate.review.store import ReviewError
from docgate.settings import PROVIDERS, Settings, SettingsError, load_settings, parse_env_file
from docgate.workflow.deps import Deps
from docgate.workflow.graph import build_graph
from docgate.workflow.runner import OperatorError, pack_number, report_of, run_packs
from docgate.workflow.state import PackState
from docgate.workflow.wiring import build_deps

SAMPLE_DIR = Path("data/sample")
DEFAULT_OUT = Path("runs/latest")
DEFAULT_GOLDEN = Path("data/golden/expected.json")
DEMO_OUT = Path("runs/demo")
DEMO_DB = Path("runs/demo.sqlite")
SMOKE_PACK = 4  # a pack with every field present, so one request exercises the whole schema


def _environment(env_file: Path = Path(".env")) -> Mapping[str, str]:
    values = parse_env_file(env_file.read_text("utf-8")) if env_file.is_file() else {}
    return {**values, **os.environ}  # real environment variables win over .env


def _packs(numbers: Sequence[int] | None) -> list[Path]:
    paths = sorted(SAMPLE_DIR.glob("supplier-pack-*.pdf"))
    if numbers:
        wanted = {f"supplier-pack-{n:02d}" for n in numbers}
        unmatched = sorted(wanted - {p.stem for p in paths})
        if unmatched:  # a typo must not quietly run fewer packs than asked for
            raise SettingsError(f"no file in {SAMPLE_DIR} for: {', '.join(unmatched)}")
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


def _deps(settings: Settings) -> Deps:
    return build_deps(settings, SAMPLE_DIR)


def _run_all(settings: Settings, packs: list[Path]) -> list[PackState]:
    """Evaluation only: in-memory checkpoints, so nothing is stored or reused between runs."""
    return run_packs(build_graph(_deps(settings)), packs)


def _pending_on(db: Path, deps: Deps) -> list[str]:
    try:
        with sqlite_saver(db) as saver:
            store = GraphReviewStore(build_graph(deps, checkpointer=saver), saver)
            return [item.pack_id for item in store.pending()]
    except sqlite3.DatabaseError as exc:
        raise ReviewError(
            f"{db} is not a readable checkpoint database ({exc}); delete it or choose --db"
        ) from exc


def _run_and_report(
    graph: Any, store: GraphReviewStore, packs: list[Path], db: Path, out: Path
) -> list[PackState]:
    on_record = set(store.pack_ids())
    for path in packs:
        if path.stem in on_record:  # re-running would silently restart a paused pack
            print(f"{path.stem:<20} already on record in {db}; skipped")
    states = run_packs(graph, [p for p in packs if p.stem not in on_record])
    for s in states:
        r = report_of(s)
        note = "  [awaiting review]" if "__interrupt__" in s else ""
        print(f"{s['pack_id']:<20} {r.decision.value:<26} {r.headline}{note}")
    write_run([report_of(s) for s in store.states()], out)
    return states


def cmd_run(settings: Settings, packs: list[Path], out: Path, db: Path, resume: bool) -> int:
    deps = _deps(settings)  # before the file is opened: a config error must not create a database
    if not resume:
        start_fresh(db, lambda: _pending_on(db, deps))
    with sqlite_saver(db) as saver:
        graph = build_graph(deps, checkpointer=saver)
        _run_and_report(graph, GraphReviewStore(graph, saver), packs, db, out)
    print(f"reports written to {out}")
    return 0


def cmd_demo(settings: Settings, out: Path, db: Path) -> int:
    """All packs from the recordings, on a database of its own that is always rebuilt."""
    offline = replace(settings, provider="replay", groq_api_key=None)  # no key, no network
    packs = _packs(None)
    deps = _deps(offline)
    discard(db)  # demo owns this file; unlike `run` there is nothing of the user's to protect
    with sqlite_saver(db) as saver:
        graph = build_graph(deps, checkpointer=saver)
        store = GraphReviewStore(graph, saver)
        states = _run_and_report(graph, store, packs, db, out)
        tally = Counter(report_of(s).decision.value for s in states)
        summary = ", ".join(f"{n} {d}" for d, n in sorted(tally.items()))
        print(f"\n{len(states)} packs: {summary}")
        print(render_pending(store.pending()))
    print(f"reports written to {out}")
    print(
        "resolve one with: python tasks.py review resolve <pack> --decision approve "
        f'--reason "..." --db {db}'
    )
    return 0


def cmd_eval(settings: Settings, packs: list[Path], out: Path, golden_file: Path) -> int:
    golden = load_golden(golden_file)
    states = _run_all(settings, packs)
    write_run([report_of(s) for s in states], out)
    # The automatic decision only: a later human decision must not mask a wrong verdict.
    actual: dict[int, Decision] = {pack_number(s["pack_id"]): s["verdict"].decision for s in states}
    result = score(golden, actual)
    print(render_report(result))
    (out / "eval.json").write_text(
        json.dumps(result_to_dict(result), indent=2) + "\n", encoding="utf-8"
    )
    return 0 if result.passed else 1


def _existing_db(db: Path) -> Path:
    if not db.is_file():  # opening would create an empty file and hide the real problem
        raise SettingsError(f"no checkpoint database at {db}; run `python tasks.py run` first")
    return db


def cmd_review(args: argparse.Namespace) -> int:
    with sqlite_saver(_existing_db(args.db)) as saver:
        settings = replace(load_settings(_environment()), provider="replay")  # never live
        graph = build_graph(_deps(settings), checkpointer=saver)
        store = GraphReviewStore(graph, saver)
        if args.action == "list":
            print(render_pending(store.pending()))
        elif args.action == "show":
            print(render_status(store.status(args.pack)))
        else:
            decision = Decision(args.decision.capitalize())
            store.resolve(args.pack, decision, args.reason, args.reviewer)
            write_run([report_of(s) for s in store.states()], args.out)
            print(f"{args.pack}: {args.decision} by {args.reviewer}; reports in {args.out}")
    return 0


def cmd_serve(settings: Settings, args: argparse.Namespace) -> int:
    import uvicorn  # only `serve` needs it

    opts = ServeOptions(
        db=args.db,
        out_dir=args.out,
        web_dist=args.web_dist,
        host=args.host,
        port=args.port,
        step_delay_s=args.step_delay,
        reviewer=getpass.getuser(),
    )
    app = build_app(replace(settings, provider=args.provider), opts)  # config errors stop here
    if not is_loopback(args.host):
        print(
            f"warning: serving on {args.host}; this API has no authentication, so anyone who can "
            "reach it can record review decisions",
            file=sys.stderr,
        )
    print(f"docgate API on http://{args.host}:{args.port} (provider: {args.provider})", flush=True)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def cmd_openapi(settings: Settings, out: Path) -> int:
    text = openapi_text(settings, ServeOptions())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="")
    print(f"wrote {out}")
    return 0


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
    helps = {"run": "run the pipeline and write reports", "eval": "score the golden set"}
    for name, text in helps.items():
        cmd = sub.add_parser(name, help=text)
        cmd.add_argument("--out", type=Path, default=DEFAULT_OUT, help="report directory")
        # Replay unless asked: a stray DOCGATE_PROVIDER=groq in .env must never spend requests.
        cmd.add_argument("--provider", choices=PROVIDERS, default="replay")
        if name == "run":
            cmd.add_argument("--db", type=Path, default=DEFAULT_DB, help="checkpoint database")
            cmd.add_argument(
                "--resume",
                action="store_true",
                help="keep the existing database (default: start from an empty one)",
            )
            cmd.add_argument("--pack", type=int, action="append", help="pack number, repeatable")
        else:
            cmd.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    demo = sub.add_parser("demo", help="run all packs from the recordings: no key, no network")
    demo.add_argument("--out", type=Path, default=DEMO_OUT, help="report directory")
    demo.add_argument("--db", type=Path, default=DEMO_DB, help="demo checkpoint database")
    srv = sub.add_parser("serve", help="serve the API (and web/dist when built) on localhost")
    srv.add_argument("--host", default="127.0.0.1", help="default: loopback only")
    srv.add_argument("--port", type=int, default=8000)
    # Replay unless asked, like `run`: a stray DOCGATE_PROVIDER=groq must not spend requests.
    srv.add_argument("--provider", choices=PROVIDERS, default="replay")
    srv.add_argument("--db", type=Path, default=ServeOptions.db, help="checkpoint database")
    srv.add_argument("--out", type=Path, default=ServeOptions.out_dir, help="report directory")
    srv.add_argument("--web-dist", type=Path, default=ServeOptions.web_dist)
    srv.add_argument(
        "--step-delay", type=float, default=0.0, help="seconds between steps, to watch a demo"
    )
    oa = sub.add_parser("openapi", help="write the API contract for the front end's type generator")
    oa.add_argument("--out", type=Path, default=OPENAPI_FILE)
    rev = sub.add_parser("review", help="list, show and resolve packs waiting for a person")
    actions = rev.add_subparsers(dest="action", required=True)
    for action in ("list", "show", "resolve"):
        act = actions.add_parser(action)
        act.add_argument("--db", type=Path, default=DEFAULT_DB, help="checkpoint database")
        if action != "list":
            act.add_argument("pack", help="pack id, e.g. supplier-pack-09")
        if action == "resolve":
            act.add_argument("--decision", choices=["approve", "reject"], required=True)
            act.add_argument("--reason", required=True, help="why; must not be empty")
            act.add_argument("--reviewer", default=getpass.getuser(), help="default: OS username")
            act.add_argument("--out", type=Path, default=DEFAULT_OUT, help="report directory")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(_environment())
        if args.command == "review":
            return cmd_review(args)
        if args.command == "serve":
            return cmd_serve(settings, args)
        if args.command == "openapi":
            return cmd_openapi(settings, args.out)
        if args.command == "demo":
            return cmd_demo(settings, args.out, args.db)
        if args.command in ("run", "eval"):
            settings = replace(settings, provider=args.provider)
            if args.command == "run":
                return cmd_run(settings, _packs(args.pack), args.out, args.db, args.resume)
            return cmd_eval(settings, _packs(None), args.out, args.golden)
        if args.command == "extract":
            return cmd_extract(settings, _packs(args.pack))
        return cmd_record(settings, _packs([SMOKE_PACK] if args.smoke else args.pack), args.force)
    except (
        SettingsError,
        LLMConfigError,
        OperatorError,
        GoldenError,
        ReviewError,
        PurchaseRequestError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
