"""CORS, host checks, secrets and the static front end."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fastapi.testclient import TestClient

from docgate.api.config import ApiConfig
from tests.api.conftest import Built
from tests.api.test_basics import error_of

Build = Callable[..., Built]
VITE = "http://localhost:5173"


def preflight(b: Built, origin: str, method: str = "POST") -> tuple[int, str | None]:
    res = b.client.options(
        "/api/runs",
        headers={"Origin": origin, "Access-Control-Request-Method": method},
    )
    return res.status_code, res.headers.get("access-control-allow-origin")


def test_cors_allows_only_the_vite_dev_origin(build: Build) -> None:
    b = build()
    assert preflight(b, VITE) == (200, VITE)
    assert preflight(b, "http://127.0.0.1:5173")[1] == "http://127.0.0.1:5173"
    for origin in ("http://evil.example", "http://localhost:5174", "null"):
        code, allowed = preflight(b, origin)
        assert allowed is None, origin
        assert code == 400
    assert preflight(b, VITE, "DELETE")[0] == 400  # only GET and POST exist
    simple = b.client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in simple.headers
    assert "access-control-allow-credentials" not in simple.headers


def test_a_foreign_host_header_is_refused(build: Build) -> None:
    b = build(allowed_hosts=("localhost", "127.0.0.1", "[::1]"))
    assert TestClient(b.app, base_url="http://localhost").get("/api/health").status_code == 200
    rebinding = TestClient(b.app, base_url="http://attacker.example").get("/api/health")
    assert rebinding.status_code == 400


def test_no_response_contains_the_api_key(build: Build) -> None:
    secret = "gsk_TOPSECRET_do_not_leak"
    b = build()
    b.run([9])
    seen = [
        b.client.get(u).text
        for u in ("/api/health", "/api/packs", "/api/packs/supplier-pack-09", "/api/review")
    ]
    seen.append(b.client.get("/openapi.json").text)
    assert not any(secret in text for text in seen)
    from docgate.settings import Settings

    assert secret not in repr(Settings(groq_api_key=secret))


def test_without_a_build_the_root_explains_instead_of_failing(build: Build) -> None:
    res = build().client.get("/")
    assert res.status_code == 200
    assert "not built" in res.text.lower() and "/docs" in res.text
    assert error_of(build().client.get("/some/page"))["code"] == "not_found"


def test_a_built_front_end_is_served_with_a_spa_fallback(build: Build, tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>APP</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the dist folder", encoding="utf-8")
    b = build(web_dist=dist)
    assert "APP" in b.client.get("/").text
    assert b.client.get("/assets/app.js").text == "console.log(1)"
    assert "APP" in b.client.get("/pack/supplier-pack-09").text  # client-side route
    assert b.client.get("/api/health").json()["web_built"] is True
    assert error_of(b.client.get("/api/nope"))["code"] == "not_found"  # never the HTML page
    leak = b.client.get("/..%2fsecret.txt")
    assert "outside the dist folder" not in leak.text


def test_the_default_config_binds_to_loopback_only() -> None:
    cfg = ApiConfig(
        web_dist=Path("web/dist"), mutation_file=Path("x"), provider="replay", model=None
    )
    assert cfg.host == "127.0.0.1"
    assert set(cfg.cors_origins) == {"http://localhost:5173", "http://127.0.0.1:5173"}
