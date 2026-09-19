"""Case parsing + specialist ranking + trial lookup.

Each piece is a seam for the real thing:
  parse_case()         -> Claude API (structured output over the case notes)
  rank_specialists()   -> Claude for "fit" scoring; the rules layer below stays as a guardrail
  find_trials()        -> ClinicalTrials.gov API v2
  distance_km()        -> Google Maps Distance Matrix API
These run inline for the mock. In production they move into Celery tasks and the
API returns a job id the frontend polls (TanStack Query refetchInterval).
"""
from math import asin, cos, radians, sin, sqrt
from typing import List, Optional

from .. import store
from ..models import Case, ParsedCase, Slot, Specialist, SpecialistMatch, Trial, User

# --- mock "AI" parse ---------------------------------------------------------
_KEYWORDS = {
    "Cardiology": ["heart", "cardiac", "bnp", "ef ", "dyspnea", "arrhythmia", "chest pain"],
    "Oncology": ["cancer", "tumor", "mass", "lymphoma", "biopsy", "malignan", "carcinoma"],
    "Neurology": ["seizure", "migraine", "stroke", "headache", "neuro", "epilep"],
}
_CONDITIONS = {"Cardiology": "Heart failure", "Oncology": "Cancer", "Neurology": "Neurological disorder"}


def parse_case(case: Case) -> ParsedCase:
    text = case.notes.lower()
    scores = {spec: [k for k in kws if k in text] for spec, kws in _KEYWORDS.items()}
    specialty = max(scores, key=lambda s: len(scores[s]))
    hits = scores[specialty]
    if not hits:
        specialty = "Internal Medicine"
    return ParsedCase(
        condition=_CONDITIONS.get(specialty, "Unspecified"),
        specialty=specialty,
        keywords=[h.strip() for h in hits],
    )


# --- distance ----------------------------------------------------------------
def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1, lng1, lat2, lng2 = map(radians, (lat1, lng1, lat2, lng2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lng2 - lng1) / 2) ** 2
    return round(6371 * 2 * asin(sqrt(a)), 1)


# --- rules guardrail -----------------------------------------------------------
MAX_KM_BY_URGENCY = {"routine": 1000.0, "urgent": 400.0, "emergent": 150.0}


def passes_guardrails(case: Case, parsed: ParsedCase, spec: Specialist, dist: float) -> bool:
    """Plain conditional logic so the AI can't recommend something clinically silly."""
    if not spec.accepting_referrals:
        return False
    if spec.specialty != parsed.specialty:
        return False
    if dist > MAX_KM_BY_URGENCY[case.urgency]:
        return False
    return True


def _next_slot(specialist_id: str) -> Optional[Slot]:
    open_slots = sorted(
        (s for s in store.SLOTS.values() if s.specialist_id == specialist_id and not s.booked),
        key=lambda s: s.starts_at,
    )
    return open_slots[0] if open_slots else None


def rank_specialists(case: Case, parsed: ParsedCase, origin: User) -> List[SpecialistMatch]:
    matches = []
    for spec in store.SPECIALISTS.values():
        dist = distance_km(origin.lat, origin.lng, spec.lat, spec.lng)
        if not passes_guardrails(case, parsed, spec, dist):
            continue
        sub_hits = [k for k in parsed.keywords if any(k in sub for sub in spec.subspecialties)]
        proximity = max(0.0, 1 - dist / MAX_KM_BY_URGENCY[case.urgency])
        score = round(min(1.0, 0.5 + 0.3 * proximity + 0.2 * bool(sub_hits)), 2)
        matches.append(
            SpecialistMatch(
                specialist=spec,
                score=score,
                distance_km=dist,
                rationale="%s specialist, %.0f km away%s."
                % (spec.specialty, dist, ", subspecialty overlap: " + ", ".join(sub_hits) if sub_hits else ""),
                next_slot=_next_slot(spec.id),
            )
        )
    return sorted(matches, key=lambda m: m.score, reverse=True)


# --- trials ------------------------------------------------------------------
_TRIALS = {
    "Heart failure": [
        Trial(nct_id="NCT00000001", title="SGLT2 inhibitor in HFrEF", condition="Heart failure",
              phase="Phase 3", location="Richmond, VA", url="https://clinicaltrials.gov/study/NCT00000001"),
    ],
    "Cancer": [
        Trial(nct_id="NCT00000002", title="Immunotherapy combination for solid tumors", condition="Cancer",
              phase="Phase 2", location="Charlottesville, VA", url="https://clinicaltrials.gov/study/NCT00000002"),
    ],
    "Neurological disorder": [
        Trial(nct_id="NCT00000003", title="Novel anticonvulsant for focal epilepsy", condition="Neurological disorder",
              phase="Phase 2", location="Durham, NC", url="https://clinicaltrials.gov/study/NCT00000003"),
    ],
}


def find_trials(parsed: ParsedCase) -> List[Trial]:
    return _TRIALS.get(parsed.condition, [])
