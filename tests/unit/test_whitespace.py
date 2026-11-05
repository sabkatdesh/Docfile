"""Whitespace normalisation at ingest: fold layout noise, never touch tokens or field breaks."""

from __future__ import annotations

import pytest

from docgate.ingest.pdf import extract_text
from docgate.ingest.whitespace import normalise_whitespace
from docgate.workflow.graph import Deps, build_graph, run_pack
from tests.graph_support import pack_path, replay_deps


@pytest.mark.parametrize(
    ("raw", "want"),
    [
        ("a  b", "a b"),
        ("a\t\tb", "a b"),
        ("a \t b", "a b"),
        ("a\r\nb", "a\nb"),
        ("a\rb", "a\nb"),
        ("a  \nb", "a\nb"),
        ("a\t\nb", "a\nb"),
        ("  a\nb", "a\nb"),
        ("a\nb  ", "a\nb"),
        ("a\n\n\n\nb", "a\n\nb"),
        ("a\n\nb", "a\n\nb"),
        ("a\r\n\r\n\r\nb", "a\n\nb"),
        ("a\n  \n  \nb", "a\n\nb"),
    ],
)
def test_layout_noise_is_folded(raw: str, want: str) -> None:
    assert normalise_whitespace(raw) == want


@pytest.mark.parametrize(
    "text",
    [
        "Total 1,234.50",
        "VAT 15%",
        "USD 12.5",
        "Net-30 days",
        "Valid 45 days",
        "TIN: 123-456",
        "AbC",
    ],
)
def test_tokens_digits_punctuation_and_case_are_untouched(text: str) -> None:
    assert normalise_whitespace(text) == text


def test_a_single_line_break_between_fields_is_kept() -> None:
    assert normalise_whitespace("Qty\n10\nUnit price\n472.00") == "Qty\n10\nUnit price\n472.00"


def test_it_is_idempotent() -> None:
    messy = "  A  b\t\tc \r\n\r\n\r\n\r\nd 1,000.00  \r\n\te"
    once = normalise_whitespace(messy)
    assert normalise_whitespace(once) == once


@pytest.mark.parametrize("n", range(1, 11))
def test_real_pack_text_is_already_canonical_so_recording_keys_stay_stable(n: int) -> None:
    text = extract_text(pack_path(n))
    assert normalise_whitespace(text) == text


NOISE = {
    "doubled_spaces": lambda t: t.replace(" ", "  "),
    "tabs": lambda t: t.replace(" ", "\t"),
    "crlf": lambda t: t.replace("\n", "\r\n"),
    "trailing_spaces": lambda t: t.replace("\n", "   \n"),
}


@pytest.mark.parametrize("noise", sorted(NOISE))
@pytest.mark.parametrize("n", range(1, 11))
def test_noisy_pack_keeps_its_verdict_through_the_real_graph(n: int, noise: str) -> None:
    clean = run_pack(build_graph(replay_deps()), f"supplier-pack-{n:02d}", pack_path(n))
    base = replay_deps()
    deps = Deps(
        llm=base.llm,
        regex=base.regex,
        pr_lines=base.pr_lines,
        read_text=lambda p: NOISE[noise](extract_text(p)),
    )
    state = run_pack(build_graph(deps), f"supplier-pack-{n:02d}", pack_path(n))
    assert state["errors"] == []
    assert state["verdict"].decision is clean["verdict"].decision
    assert state["verdict"].rule_results == clean["verdict"].rule_results


def test_ingest_node_hands_normalised_text_to_every_reader() -> None:
    seen: dict[str, str] = {}

    class Spy:
        def __init__(self, name: str) -> None:
            self.name = name

        def extract(self, text: str, label: str = "") -> object:
            seen[self.name] = text
            raise RuntimeError("stop here")

    base = replay_deps()
    deps = Deps(
        llm=Spy("llm"),  # type: ignore[arg-type]
        regex=Spy("regex"),  # type: ignore[arg-type]
        pr_lines=base.pr_lines,
        read_text=lambda _p: "A  b\r\nC\t d  \r\n",
    )
    run_pack(build_graph(deps), "supplier-pack-01", pack_path(1))
    assert seen == {"llm": "A b\nC d", "regex": "A b\nC d"}
