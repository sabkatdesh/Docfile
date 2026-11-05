"""API settings. Plain values passed in by the caller; nothing is read from the environment here."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

VITE_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]")


@dataclass(frozen=True)
class ApiConfig:
    web_dist: Path
    mutation_file: Path
    provider: str
    model: str | None  # shown on /api/health only when live; never any credential
    host: str = "127.0.0.1"  # loopback only: there is no authentication
    port: int = 8000
    cors_origins: tuple[str, ...] = VITE_ORIGINS
    # Host header allowlist (DNS-rebinding guard): this API can record review decisions.
    allowed_hosts: tuple[str, ...] = LOOPBACK_HOSTS
    default_reviewer: str = "reviewer"
    sse_keepalive_s: float = 15.0
