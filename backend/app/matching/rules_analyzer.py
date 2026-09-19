"""Rules-only CaseAnalyzer: the fallback when Claude is unavailable.

Deliberately conservative: it never returns EXCELLENT, and it can only see keywords, so the
physician's confirmation step matters even more when this is in use.
"""

import re
from collections.abc import Sequence

from app.models.enums import Complexity, FitTier, Urgency
from app.models.match import ClinicalFit
from app.models.people import Specialist
from app.models.referral import ParsedCase

SPECIALTY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Orthopedics": ("knee", "hip", "shoulder", "joint", "fracture", "acl", "meniscus", "bone"),
    "Cardiology": ("chest pain", "palpitation", "arrhythmia", "murmur", "ecg", "heart"),
    "Neurology": (
        "seizure",
        "migraine",
        "tremor",
        "numbness",
        "neuropathy",
        "weakness",
        "myopathy",
    ),
    "Pulmonology": (
        "cough",
        "dyspnea",
        "shortness of breath",
        "asthma",
        "copd",
        "pulmonary",
        "lung",
    ),
    "Dermatology": ("rash", "lesion", "mole", "psoriasis", "eczema"),
    "Endocrinology": ("thyroid", "diabetes", "insulin", "a1c", "hormone"),
}
RARE_KEYWORDS = (
    "rare",
    "orphan",
    "refractory",
    "undiagnosed",
    "genetic",
    "atypical",
    "nondiagnostic",
)
URGENT_KEYWORDS = ("sudden", "severe", "acute", "worsening", "emergent", "radiating")
RED_FLAG_KEYWORDS = ("syncope", "chest pain", "radiating", "hemoptysis", "fever", "weight loss")


def _found(text: str, keywords: Sequence[str]) -> list[str]:
    return [k for k in keywords if re.search(rf"\b{re.escape(k)}", text)]


class RulesAnalyzer:
    async def parse_case(
        self, case_notes: str, urgency: Urgency, known_specialties: Sequence[str] = ()
    ) -> ParsedCase:
        text = case_notes.lower()
        specialties, tags = [], []
        for specialty, keywords in SPECIALTY_KEYWORDS.items():
            hits = _found(text, keywords)
            if hits:
                specialties.append(specialty)
                tags.extend(hits)
        suggested_urgency = Urgency.URGENT if _found(text, URGENT_KEYWORDS) else urgency
        rare = bool(_found(text, RARE_KEYWORDS))
        return ParsedCase(
            condition_summary=case_notes.strip().split(".")[0][:200],
            suggested_specialties=specialties,
            subspecialty_tags=tags,
            red_flags=_found(text, RED_FLAG_KEYWORDS),
            suggested_urgency=suggested_urgency,
            suggested_complexity=Complexity.RARE_COMPLEX if rare else Complexity.ROUTINE,
            rationale="Keyword-based fallback (Claude unavailable); please review carefully.",
            source="rules_fallback",
        )

    async def assess_fit(
        self, parsed: ParsedCase, specialists: Sequence[Specialist]
    ) -> dict[str, ClinicalFit]:
        wanted = {s.lower() for s in parsed.suggested_specialties}
        tags = {t.lower() for t in parsed.subspecialty_tags}
        fits = {}
        for sp in specialists:
            if sp.specialty.lower() not in wanted:
                fits[sp.id] = ClinicalFit(
                    tier=FitTier.POOR, rationale=f"{sp.specialty} does not match the case"
                )
                continue
            overlap = sorted(tags & {s.lower() for s in sp.subspecialties})
            if overlap:
                fits[sp.id] = ClinicalFit(
                    tier=FitTier.GOOD,
                    rationale=(
                        f"{sp.specialty}; subspecialty overlaps with the case "
                        f"({', '.join(overlap)})"
                    ),
                )
            else:
                fits[sp.id] = ClinicalFit(
                    tier=FitTier.PARTIAL,
                    rationale=f"{sp.specialty} matches, but no subspecialty overlap was found",
                )
        return fits
