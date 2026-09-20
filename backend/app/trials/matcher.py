"""Keyword matching between a parsed case and the mocked trial list. Pure, deterministic --
mirrors the keyword-overlap style already used by app.matching.rules_analyzer, rather than
another Claude call: trials are a discussion option the physician vets, not a scored ranking."""

from app.models.referral import ParsedCase
from app.models.trials import Trial
from app.trials.data import TRIALS


def match_trials(parsed: ParsedCase) -> list[Trial]:
    tags = {t.lower() for t in parsed.subspecialty_tags}
    specialties = {s.lower() for s in parsed.suggested_specialties}
    wanted = tags | specialties
    return [t for t in TRIALS if wanted & {k.lower() for k in t.condition_keywords}]
