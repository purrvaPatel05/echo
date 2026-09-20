import pytest

from app.matching import config
from app.matching.scoring import (
    availability_score,
    distance_score,
    fit_score,
    insurance_score,
    within_urgency_window,
)
from app.models.enums import FitTier, InsuranceStatus, Urgency


@pytest.mark.parametrize(
    "weights",
    list(config.WEIGHT_PROFILES.values()),
)
def test_weight_profiles_sum_to_one(weights):
    assert sum(weights.values()) == pytest.approx(1.0)


def test_gated_values_have_no_score():
    assert fit_score(FitTier.POOR) is None
    assert insurance_score(InsuranceStatus.NOT_ACCEPTED) is None


def test_insurance_ordering():
    assert (
        insurance_score(InsuranceStatus.IN_NETWORK)
        > insurance_score(InsuranceStatus.UNVERIFIED)
        > insurance_score(InsuranceStatus.OUT_OF_NETWORK)
    )


@pytest.mark.parametrize(
    ("miles", "expected"),
    [(0, 1.0), (5, 1.0), (27.5, 0.5), (50, 0.0), (120, 0.0)],
)
def test_distance_score_linear(miles, expected):
    assert distance_score(miles) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("days", "urgency", "expected"),
    [
        (0, Urgency.URGENT, 1.0),
        (1, Urgency.URGENT, 2 / 3),
        (3, Urgency.URGENT, 0.0),
        (7, Urgency.SOON, 0.5),
        (60, Urgency.ROUTINE, 0.0),
    ],
)
def test_availability_score_linear_over_window(days, urgency, expected):
    assert availability_score(days, urgency) == pytest.approx(expected)


def test_urgency_window_gate():
    assert within_urgency_window(3, Urgency.URGENT)
    assert not within_urgency_window(4, Urgency.URGENT)
    assert within_urgency_window(60, Urgency.ROUTINE)
