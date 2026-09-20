"""What the frontend's trials table shows that the core's synthetic trials don't carry: recruitment
status, the intervention, and a site location. Keyed by the core trial id; synthetic like the
trials themselves (the NCT ids are not real registrations, so the ClinicalTrials.gov links do not
resolve to real studies)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrialInfo:
    status: str  # recruiting | not_yet_recruiting | active_not_recruiting
    intervention: str
    site: str  # display, "City, ST"
    lat: float
    lng: float


TRIAL_INFO: dict[str, TrialInfo] = {
    "trial_myopathy_01": TrialInfo(
        "recruiting", "Drug: targeted immunomodulator", "Boston, MA", 42.3601, -71.0589
    ),
    "trial_pah_01": TrialInfo(
        "recruiting",
        "Drug: add-on therapy to background treatment",
        "Boston, MA",
        42.3601,
        -71.0589,
    ),
    "trial_arrhythmia_01": TrialInfo(
        "not_yet_recruiting",
        "Procedure: catheter ablation, two techniques compared",
        "Cambridge, MA",
        42.3736,
        -71.1097,
    ),
    "trial_neuropathy_01": TrialInfo(
        "active_not_recruiting",
        "Genetic: expanded genetic screening",
        "Worcester, MA",
        42.2626,
        -71.8023,
    ),
}
