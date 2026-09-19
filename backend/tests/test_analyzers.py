from types import SimpleNamespace

import pytest

from app.matching.claude_analyzer import (
    AnalyzerError,
    ClaudeAnalyzer,
    _FitItem,
    _FitOut,
    _ParseOut,
)
from app.matching.rules_analyzer import RulesAnalyzer
from app.matching.service import Analyzers, match, parse_case
from app.matching.types import Candidate
from app.models.enums import Complexity, FitTier, InsuranceStatus, Urgency
from app.models.match import ClinicalFit, InsuranceCheck
from app.seed.data import DEMO_CASES, SPECIALISTS

CASES = {c.referral_id: c for c in DEMO_CASES}
SPECIALTIES = sorted({s.specialty for s in SPECIALISTS})


# ---- rules-only fallback -------------------------------------------------------------------


async def test_rules_parse_maps_specialty_and_flags():
    knee = await RulesAnalyzer().parse_case(CASES["ref_demo_knee"].notes, Urgency.ROUTINE)
    assert knee.suggested_specialties == ["Orthopedics"]
    assert knee.suggested_complexity == Complexity.ROUTINE
    assert knee.source == "rules_fallback"

    rare = await RulesAnalyzer().parse_case(CASES["ref_demo_rare_neuro"].notes, Urgency.ROUTINE)
    assert "Neurology" in rare.suggested_specialties
    assert rare.suggested_complexity == Complexity.RARE_COMPLEX

    chest = await RulesAnalyzer().parse_case(CASES["ref_demo_urgent_chest"].notes, Urgency.SOON)
    assert "Cardiology" in chest.suggested_specialties
    assert chest.suggested_urgency == Urgency.URGENT


async def test_rules_fit_gates_wrong_specialty_and_never_says_excellent():
    parsed = await RulesAnalyzer().parse_case(CASES["ref_demo_knee"].notes, Urgency.ROUTINE)
    fits = await RulesAnalyzer().assess_fit(parsed, SPECIALISTS)
    assert fits["sp_chen"].tier == FitTier.GOOD  # knee subspecialty overlaps
    assert fits["sp_park"].tier == FitTier.PARTIAL  # right specialty, no overlap
    assert fits["sp_okafor"].tier == FitTier.POOR
    assert FitTier.EXCELLENT not in {f.tier for f in fits.values()}


# ---- Claude analyzer against a stub client ---------------------------------------------------


class StubMessages:
    def __init__(self, outputs, stop_reason="end_turn"):
        self.outputs, self.stop_reason, self.calls = list(outputs), stop_reason, []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.outputs.pop(0), stop_reason=self.stop_reason)


def _stub(*outputs, stop_reason="end_turn"):
    return SimpleNamespace(messages=StubMessages(outputs, stop_reason))


async def test_claude_parse_case_builds_parsed_case():
    out = _ParseOut(
        condition_summary="Knee osteoarthritis",
        suggested_specialties=["Orthopedics"],
        subspecialty_tags=["knee"],
        red_flags=[],
        suggested_urgency=Urgency.ROUTINE,
        suggested_complexity=Complexity.ROUTINE,
        rationale="Classic presentation",
    )
    client = _stub(out)
    parsed = await ClaudeAnalyzer(client, "claude-opus-5").parse_case(
        "notes", Urgency.ROUTINE, SPECIALTIES
    )
    assert parsed.source == "claude" and parsed.condition_summary == "Knee osteoarthritis"
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["output_format"] is _ParseOut
    assert call["extra_body"] == {"fallbacks": "default"}


async def test_claude_fit_drops_invented_ids_and_can_skip_server_fallback():
    out = _FitOut(
        assessments=[
            _FitItem(specialist_id="sp_chen", tier=FitTier.EXCELLENT, rationale="Knee expert"),
            _FitItem(specialist_id="sp_ghost", tier=FitTier.EXCELLENT, rationale="Invented"),
        ]
    )
    client = _stub(out)
    parsed = await RulesAnalyzer().parse_case(CASES["ref_demo_knee"].notes, Urgency.ROUTINE)
    fits = await ClaudeAnalyzer(client, "m", server_fallback=False).assess_fit(parsed, SPECIALISTS)
    assert set(fits) == {"sp_chen"}
    assert "extra_body" not in client.messages.calls[0]


async def test_claude_refusal_raises():
    client = _stub(None, stop_reason="refusal")
    with pytest.raises(AnalyzerError):
        await ClaudeAnalyzer(client, "m").parse_case("notes", Urgency.ROUTINE)


# ---- graceful degradation --------------------------------------------------------------------


class ExplodingAnalyzer:
    async def parse_case(self, *a, **k):
        raise RuntimeError("network blip")

    async def assess_fit(self, *a, **k):
        raise RuntimeError("network blip")


class ScriptedAnalyzer(RulesAnalyzer):
    async def assess_fit(self, parsed, specialists):
        return {
            s.id: ClinicalFit(tier=FitTier.EXCELLENT, rationale="scripted") for s in specialists
        }


def _candidates():
    return [
        Candidate(
            specialist=s,
            distance_miles=5,
            insurance=InsuranceCheck(status=InsuranceStatus.IN_NETWORK, detail="x"),
            days_until_slot=2,
        )
        for s in SPECIALISTS
        if s.specialty == "Orthopedics"
    ]


async def test_parse_falls_back_when_claude_errors():
    analyzers = Analyzers(primary=ExplodingAnalyzer(), fallback=RulesAnalyzer())
    parsed = await parse_case(analyzers, CASES["ref_demo_knee"].notes, Urgency.ROUTINE, [])
    assert parsed.source == "rules_fallback"


@pytest.mark.parametrize("primary", [ExplodingAnalyzer(), None])
async def test_match_is_flagged_degraded_when_claude_unavailable(primary):
    analyzers = Analyzers(primary=primary, fallback=RulesAnalyzer())
    parsed = await RulesAnalyzer().parse_case(CASES["ref_demo_knee"].notes, Urgency.ROUTINE)
    out = await match(analyzers, parsed, _candidates(), Urgency.ROUTINE, Complexity.ROUTINE)
    assert out.degraded is True
    assert out.outcome.results  # the demo still produces a ranked list


async def test_match_not_degraded_when_claude_works():
    analyzers = Analyzers(primary=ScriptedAnalyzer(), fallback=RulesAnalyzer())
    parsed = await RulesAnalyzer().parse_case(CASES["ref_demo_knee"].notes, Urgency.ROUTINE)
    out = await match(analyzers, parsed, _candidates(), Urgency.ROUTINE, Complexity.ROUTINE)
    assert out.degraded is False
    assert {r.clinical_fit.tier for r in out.outcome.results} == {FitTier.EXCELLENT}
