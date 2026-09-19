"""Orchestrates analyzers with graceful degradation to the rules-only fallback."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from app.matching.ranking import RankOutcome, rank_candidates
from app.matching.types import Candidate, CaseAnalyzer
from app.models.enums import Complexity, Urgency
from app.models.people import Specialist
from app.models.referral import ParsedCase

logger = logging.getLogger(__name__)


@dataclass
class Analyzers:
    """`primary` is Claude; None when no API key is configured. `fallback` is rules-only."""

    primary: CaseAnalyzer | None
    fallback: CaseAnalyzer


async def parse_case(
    analyzers: Analyzers, case_notes: str, urgency: Urgency, known_specialties: Sequence[str]
) -> ParsedCase:
    if analyzers.primary is not None:
        try:
            return await analyzers.primary.parse_case(case_notes, urgency, known_specialties)
        except Exception:
            logger.exception("Claude case parsing failed; using rules-only fallback")
    return await analyzers.fallback.parse_case(case_notes, urgency, known_specialties)


@dataclass
class MatchOutput:
    outcome: RankOutcome
    degraded: bool  # True when rules-only fit assessment was used


async def match(
    analyzers: Analyzers,
    parsed: ParsedCase,
    candidates: Sequence[Candidate],
    urgency: Urgency,
    complexity: Complexity,
) -> MatchOutput:
    specialists: list[Specialist] = [c.specialist for c in candidates]
    fits, degraded = None, True
    if analyzers.primary is not None:
        try:
            fits = await analyzers.primary.assess_fit(parsed, specialists)
            degraded = False
        except Exception:
            logger.exception("Claude fit assessment failed; using rules-only fallback")
    if fits is None:
        fits = await analyzers.fallback.assess_fit(parsed, specialists)
    return MatchOutput(rank_candidates(candidates, fits, urgency, complexity), degraded)
