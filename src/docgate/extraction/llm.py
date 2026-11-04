"""LLM reader. It proposes values with quotes; it never decides anything."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from pydantic import ValidationError

from docgate.domain.config import DEFAULT_CONFIG, RuleConfig
from docgate.extraction.base import Candidate, ExtractorOutput, absent, found, unreadable
from docgate.extraction.derive import derive_vat_flag
from docgate.extraction.parsing import FIELD_PARSERS, ParseError
from docgate.extraction.prompt import Prompt
from docgate.extraction.wire import (
    SCHEMA_VERSION,
    WIRE_FIELDS,
    WireExtraction,
    WireField,
    strict_json_schema,
)
from docgate.llm.provider import (
    LLMBadResponseError,
    LLMConfigError,
    LLMError,
    LLMProvider,
    LLMRequest,
)

_SCHEMA_NAME = "supplier_quotation_extraction"
_ATTEMPTS = 2  # spec: malformed output retries once, then escalates
_INCLUSIVE = "tax_inclusive_statement"


def _blank(s: str | None) -> bool:
    return s is None or not s.strip()


class LLMExtractor:
    name = "llm"

    def __init__(
        self,
        provider: LLMProvider,
        prompt: Prompt,
        params: Mapping[str, str],
        cfg: RuleConfig = DEFAULT_CONFIG,
    ) -> None:
        self._provider = provider
        self._prompt = prompt
        self._params = dict(params)
        self._cfg = cfg

    def extract(self, text: str, label: str = "") -> ExtractorOutput:
        request = LLMRequest(
            system=self._prompt.text,
            user=f"<document>\n{text}\n</document>",
            schema=strict_json_schema(),
            schema_name=_SCHEMA_NAME,
            prompt_version=self._prompt.version,
            schema_version=SCHEMA_VERSION,
            params=self._params,
            label=label,
        )
        base_user = request.user
        problem = "no attempt made"
        for _ in range(_ATTEMPTS):
            try:
                raw = self._provider.complete_json(request)
            except LLMConfigError:
                raise  # operator problem (bad key, budget): stop the run, do not escalate packs
            except LLMBadResponseError as exc:
                problem = f"request rejected: {exc}"
            except LLMError as exc:
                return self._failed(str(exc))  # transport retries are already exhausted
            else:
                try:
                    wire = WireExtraction.model_validate_json(raw)
                except ValidationError as exc:
                    problem = f"invalid response: {_short(exc)}"
                else:
                    return ExtractorOutput(source=self.name, candidates=self._candidates(wire))
            request = replace(
                request,
                user=f"{base_user}\n\nYour previous response was invalid ({problem}). "
                "Return only valid JSON that matches the schema.",
            )
        return self._failed(f"no valid response after {_ATTEMPTS} attempts: {problem}")

    def _failed(self, reason: str) -> ExtractorOutput:
        return ExtractorOutput(source=self.name, failure=reason)

    def _candidates(self, wire: WireExtraction) -> dict[str, Candidate]:
        out = {
            name: self._candidate(name, getattr(wire, name))
            for name in WIRE_FIELDS
            if name != _INCLUSIVE
        }
        inclusive = wire.tax_inclusive_statement
        incl = (
            absent()
            if _blank(inclusive.value) and _blank(inclusive.quote)
            else found(True, inclusive.quote or "", raw=inclusive.value)
            if not _blank(inclusive.value) and not _blank(inclusive.quote)
            else unreadable("incomplete tax-inclusive claim", inclusive.quote)
        )
        out["vat_shown_separately"] = derive_vat_flag(out["vat_amount"], incl)
        return out

    def _candidate(self, name: str, wf: WireField) -> Candidate:
        if _blank(wf.value) and _blank(wf.quote):
            return absent("the model reports it is not stated")
        if _blank(wf.value) or _blank(wf.quote):
            return unreadable("value and quote must come together", wf.quote)
        assert wf.value is not None and wf.quote is not None  # narrowed by _blank above
        try:
            parsed = FIELD_PARSERS[name](wf.value, self._cfg)
        except ParseError as exc:
            return unreadable(str(exc), wf.quote)
        return found(parsed, wf.quote, raw=wf.value)


def _short(exc: ValidationError) -> str:
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"]) or "document"
    return f"{where}: {first['msg']}"[:200]
