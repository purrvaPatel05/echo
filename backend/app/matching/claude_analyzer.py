"""Claude-backed CaseAnalyzer: structured outputs, no free-text parsing."""

import json
import logging
from collections.abc import Sequence

from pydantic import BaseModel

from app.models.enums import Complexity, FitTier, Urgency
from app.models.match import ClinicalFit
from app.models.people import Specialist
from app.models.referral import ParsedCase

logger = logging.getLogger(__name__)

# Server-side fallback re-runs a safety-declined request on another model inside the same call.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

PARSE_SYSTEM = """You help a referring physician structure a patient case for specialist matching.
You do not diagnose and you do not choose a specialist; you extract and suggest, and the
physician reviews everything.
- suggested_specialties must come from the provided list of known specialties when any fits.
- subspecialty_tags are short lowercase phrases (e.g. "knee", "neuromuscular").
- suggested_complexity is rare_complex only for rare, undiagnosed, or treatment-refractory
  presentations; otherwise routine.
- red_flags are findings in the notes that suggest urgency; leave empty if none."""

FIT_SYSTEM = """You assess clinical fit between a structured patient case and each specialist.
Rate every specialist with one tier:
- excellent: specialty and subspecialty directly match the presenting problem
- good: right specialty, subspecialty partly relevant
- partial: right specialty, but subspecialty is not particularly relevant
- poor: specialty does not fit the case
Give a one-sentence rationale a physician would find credible. Judge clinical fit only; ignore
distance, insurance, and scheduling. Return one assessment per specialist, using the exact ids."""


class _ParseOut(BaseModel):
    condition_summary: str
    suggested_specialties: list[str]
    subspecialty_tags: list[str]
    red_flags: list[str]
    suggested_urgency: Urgency
    suggested_complexity: Complexity
    rationale: str


class _FitItem(BaseModel):
    specialist_id: str
    tier: FitTier
    rationale: str


class _FitOut(BaseModel):
    assessments: list[_FitItem]


class AnalyzerError(Exception):
    pass


class ClaudeAnalyzer:
    def __init__(self, client, model: str, *, server_fallback: bool = True):
        self._client = client  # an anthropic.AsyncAnthropic (or a test double)
        self._model = model
        self._extra = (
            {
                "extra_headers": {"anthropic-beta": _FALLBACK_BETA},
                "extra_body": {"fallbacks": "default"},
            }
            if server_fallback
            else {}
        )

    async def _parse(self, system: str, payload: dict, output_format: type[BaseModel]):
        response = await self._client.messages.parse(
            model=self._model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload)}],
            output_format=output_format,
            **self._extra,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise AnalyzerError(
                f"Claude returned no usable output (stop_reason={response.stop_reason})"
            )
        return response.parsed_output

    async def parse_case(
        self, case_notes: str, urgency: Urgency, known_specialties: Sequence[str] = ()
    ) -> ParsedCase:
        out = await self._parse(
            PARSE_SYSTEM,
            {
                "case_notes": case_notes,
                "physician_stated_urgency": urgency.value,
                "known_specialties": list(known_specialties),
            },
            _ParseOut,
        )
        return ParsedCase(**out.model_dump(), source="claude")

    async def assess_fit(
        self, parsed: ParsedCase, specialists: Sequence[Specialist]
    ) -> dict[str, ClinicalFit]:
        out = await self._parse(
            FIT_SYSTEM,
            {
                "case": parsed.model_dump(mode="json", exclude={"source"}),
                "specialists": [
                    {
                        "id": s.id,
                        "specialty": s.specialty,
                        "subspecialties": s.subspecialties,
                    }
                    for s in specialists
                ],
            },
            _FitOut,
        )
        known = {s.id for s in specialists}
        # Ignore ids Claude invented; anything it skipped falls through to POOR in the ranker.
        return {
            a.specialist_id: ClinicalFit(tier=a.tier, rationale=a.rationale)
            for a in out.assessments
            if a.specialist_id in known
        }
