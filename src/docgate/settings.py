"""Configuration from environment variables. Pure: the caller supplies the mapping."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PROVIDERS = ("replay", "groq")
EFFORTS = ("low", "medium", "high")
STRUCTURED_MODES = ("strict", "best_effort", "json_object")


class SettingsError(Exception):
    """A configuration value is invalid."""


class MissingApiKeyError(SettingsError):
    pass


@dataclass(frozen=True)
class Settings:
    provider: str = "replay"
    # repr=False so the key can never leak through logging or a traceback of this object.
    groq_api_key: str | None = field(default=None, repr=False)
    groq_model: str = "openai/gpt-oss-120b"
    reasoning_effort: str = "low"
    structured_mode: str = "strict"
    recorded_dir: Path = Path("data/recorded")
    timeout_s: float = 30.0
    # Free tier allows 8K tokens/min; one pack costs about 3K, so space live calls out.
    min_interval_s: float = 25.0
    max_requests: int = 30
    max_completion_tokens: int = 4096

    def require_api_key(self) -> str:
        key = (self.groq_api_key or "").strip()
        if not key:
            raise MissingApiKeyError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key, "
                "or set DOCGATE_PROVIDER=replay to use the recorded responses."
            )
        return key


def _choice(env: Mapping[str, str], name: str, default: str, allowed: tuple[str, ...]) -> str:
    value = env.get(name, default).strip() or default
    if value not in allowed:
        raise SettingsError(f"{name} must be one of {', '.join(allowed)}; got {value!r}")
    return value


def load_settings(env: Mapping[str, str]) -> Settings:
    defaults = Settings()
    return Settings(
        provider=_choice(env, "DOCGATE_PROVIDER", defaults.provider, PROVIDERS),
        groq_api_key=env.get("GROQ_API_KEY") or None,
        groq_model=env.get("DOCGATE_GROQ_MODEL", "").strip() or defaults.groq_model,
        reasoning_effort=_choice(
            env, "DOCGATE_REASONING_EFFORT", defaults.reasoning_effort, EFFORTS
        ),
        structured_mode=_choice(
            env, "DOCGATE_STRUCTURED_MODE", defaults.structured_mode, STRUCTURED_MODES
        ),
        recorded_dir=Path(env.get("DOCGATE_RECORDED_DIR", "").strip() or defaults.recorded_dir),
    )


def request_params(settings: Settings) -> dict[str, str]:
    """Settings that change what the model returns. They are part of every recording key."""
    return {
        "reasoning_effort": settings.reasoning_effort,
        "structured_mode": settings.structured_mode,
        "temperature": "0",
        "max_completion_tokens": str(settings.max_completion_tokens),
    }


def parse_env_file(text: str) -> dict[str, str]:
    """Minimal KEY=VALUE parser (no dependency). Comments and malformed lines are skipped."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out
