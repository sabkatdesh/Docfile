"""Health, the pack list and detail, the PDF route (path traversal) and the error body."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from tests.api.conftest import Built

Build = Callable[..., Built]


def error_of(res: Any) -> dict[str, Any]:
    body: dict[str, Any] = res.json()
    assert set(body) == {"error"}, body
    assert {"code", "message"} <= set(body["error"])
    err: dict[str, Any] = body["error"]
    return err


def test_health_reports_mode_and_never_a_key(build: Build) -> None:
    res = build().client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {
        "status": "ok",
        "provider": "replay",
        "model": None,
        "packs": 10,
        "web_built": False,
        "active_run_id": None,
    }


def test_packs_before_any_run_are_all_not_run(build: Build) -> None:
    rows = build().client.get("/api/packs").json()
    assert [r["pack_id"] for r in rows] == [f"supplier-pack-{n:02d}" for n in range(1, 11)]
    assert {r["status"] for r in rows} == {"not_run"}
    assert rows[0]["source_file"] == "supplier-pack-01.pdf"
    assert rows[0]["decision"] is None


def test_packs_after_a_run_carry_the_verdicts(build: Build) -> None:
    b = build()
    b.run([1, 3, 9])
    rows = {r["pack_id"]: r for r in b.client.get("/api/packs").json()}
    assert rows["supplier-pack-01"]["decision"] == "Approve"
    assert rows["supplier-pack-01"]["status"] == "final"
    assert rows["supplier-pack-03"]["decision"] == "Reject"
    assert rows["supplier-pack-03"]["primary_rule"] == "R1"
    assert rows["supplier-pack-09"]["status"] == "pending_review"
    assert rows["supplier-pack-02"]["status"] == "not_run"


def test_detail_has_text_fields_comparison_rules_and_verdict(build: Build) -> None:
    b = build()
    b.run([9])
    body = b.client.get("/api/packs/supplier-pack-09").json()
    assert body["status"] == "pending_review"
    assert body["machine"]["decision"] == "Needs a person to check"
    assert body["human_review"] is None
    assert body["pdf_url"] == "/api/packs/supplier-pack-09/pdf"
    text = body["text"]
    price = next(f for f in body["fields"] if f["name"] == "unit_price")
    assert price["status"] == "OK" and price["value"]
    s = price["span"]
    shown = " ".join(text[s["start"] : s["end"]].split()).casefold()
    assert shown == " ".join(price["quote"].split()).casefold()
    rules = {r["rule_id"]: r for r in body["rules"]}
    assert rules["H3"]["status"] == "FAIL" and rules["H6"]["status"] == "FAIL"
    assert rules["R1"]["status"] == "PASS"
    cmp = body["comparison"]
    assert cmp["requested_qty"] and cmp["max_unit_price"]
    assert any(a["ok"] is False for a in cmp["arithmetic"])
    assert isinstance(cmp["price_delta_pct"], str)  # percentages are strings, never floats


def test_detail_unknown_and_not_run(build: Build) -> None:
    b = build()
    res = b.client.get("/api/packs/supplier-pack-99")
    assert res.status_code == 404 and error_of(res)["code"] == "unknown_pack"
    res = b.client.get("/api/packs/supplier-pack-02")
    assert res.status_code == 404 and error_of(res)["code"] == "no_result"


def test_pdf_is_served_for_a_listed_pack(build: Build) -> None:
    res = build().client.get("/api/packs/supplier-pack-01/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")
    assert res.headers["content-disposition"].startswith("inline")


@pytest.mark.parametrize(
    "pack_id",
    [
        "..%2f..%2fCLAUDE.md",
        "%2e%2e%2f%2e%2e%2fCLAUDE.md",
        "..%5c..%5cCLAUDE.md",
        "..",
        "%2fetc%2fpasswd",
        "C%3A%5CWindows%5Cwin.ini",
        "supplier-pack-99",
        "supplier-pack-01.pdf",
        "SUPPLIER-PACK-01",
        "supplier-pack-01%00",
    ],
)
def test_pdf_route_never_leaves_the_allowlist(build: Build, pack_id: str) -> None:
    res = build().client.get(f"/api/packs/{pack_id}/pdf")
    assert res.status_code == 404
    assert b"%PDF" not in res.content
    assert error_of(res)["code"] in {"unknown_pack", "not_found"}


def test_unknown_paths_and_wrong_methods_use_the_same_error_body(build: Build) -> None:
    b = build()
    assert error_of(b.client.get("/api/nope"))["code"] == "not_found"
    res = b.client.post("/api/packs")
    assert res.status_code == 405 and error_of(res)["code"] == "method_not_allowed"


def test_an_unhandled_exception_is_a_generic_500(build: Build) -> None:
    b = build(raise_server_exceptions=False)

    def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("secret internal detail C:\\path\\to\\key")

    b.manager.state = boom  # type: ignore[method-assign]
    res = b.client.get("/api/packs")
    assert res.status_code == 500
    assert error_of(res)["code"] == "internal_error"
    assert "secret" not in res.text and "Traceback" not in res.text
