"""Record raw model responses once, replay them forever. Replay never touches the network."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from docgate.llm.provider import LLMError, LLMProvider, LLMRequest

_KEY_PREFIX = 16


class ReplayMissError(LLMError):
    """No recording matches this request. Not retryable: re-asking cannot create one."""


def request_key(request: LLMRequest, model_id: str) -> str:
    """Everything that can change the answer. The prompt body is hashed too, so editing the
    prompt file without bumping its version still invalidates stale recordings."""
    payload = {
        "model": model_id,
        "prompt_version": request.prompt_version,
        "schema_version": request.schema_version,
        "params": dict(sorted(request.params.items())),
        "system_sha256": hashlib.sha256(request.system.encode("utf-8")).hexdigest(),
        "user": request.user,
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _find(directory: Path, key: str) -> Path | None:
    for path in sorted(directory.glob(f"*__{key[:_KEY_PREFIX]}.json")):
        if json.loads(path.read_text("utf-8")).get("key") == key:
            return path
    return None


def _read(path: Path) -> str:
    response = json.loads(path.read_text("utf-8"))["response"]
    if not isinstance(response, str):
        raise ReplayMissError(f"recording {path.name} is corrupt: response is not text")
    return response


class ReplayProvider:
    def __init__(self, directory: Path, model_id: str) -> None:
        self._dir = directory
        self.model_id = model_id

    def complete_json(self, request: LLMRequest) -> str:
        key = request_key(request, self.model_id)
        path = _find(self._dir, key) if self._dir.is_dir() else None
        if path is None:
            raise ReplayMissError(
                f"no recording for {request.label or 'this input'} (key {key[:_KEY_PREFIX]}). "
                "Inputs, prompt, model or settings changed since it was recorded; "
                "run `python tasks.py record` with a GROQ_API_KEY."
            )
        return _read(path)


class RecordingProvider:
    """Wraps a live provider. Serves an existing recording when there is one (unless
    `overwrite`), so re-running the recorder never spends requests it does not need."""

    def __init__(self, inner: LLMProvider, directory: Path, overwrite: bool = False) -> None:
        self._inner = inner
        self._dir = directory
        self._overwrite = overwrite
        self.written: list[Path] = []

    @property
    def model_id(self) -> str:
        return self._inner.model_id

    def complete_json(self, request: LLMRequest) -> str:
        key = request_key(request, self.model_id)
        existing = _find(self._dir, key) if self._dir.is_dir() else None
        if existing is not None and not self._overwrite:
            return _read(existing)
        response = self._inner.complete_json(request)
        self._write(request, key, response, existing)
        return response

    def _write(self, request: LLMRequest, key: str, response: str, existing: Path | None) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = existing or self._dir / f"{request.label or 'request'}__{key[:_KEY_PREFIX]}.json"
        record: dict[str, Any] = {
            "key": key,
            "label": request.label,
            "model": self.model_id,
            "prompt_version": request.prompt_version,
            "schema_version": request.schema_version,
            "params": dict(sorted(request.params.items())),
            "response": response,
        }
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self.written.append(path)

    def discard_written(self) -> None:
        """Failed extractions are never recorded: remove what this run just wrote."""
        for path in self.written:
            path.unlink(missing_ok=True)
        self.written.clear()
