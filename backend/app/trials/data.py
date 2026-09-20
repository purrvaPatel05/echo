"""Synthetic trial data standing in for a live ClinicalTrials.gov API call. Nothing here is
real: ids, titles, and eligibility text are all made up for the demo."""

from app.models.trials import Trial

TRIALS: list[Trial] = [
    Trial(
        id="trial_myopathy_01",
        nct_id="NCT05010001",
        title="Investigational Therapy for Inflammatory Myopathies",
        phase="Phase 2",
        condition="Inflammatory myopathy / neuromuscular disorder",
        condition_keywords=["myopathy", "weakness", "neuromuscular", "muscle"],
        summary="Testing a targeted immunomodulator in adults with an inflammatory or "
        "undiagnosed neuromuscular myopathy who haven't responded to standard workup.",
        eligibility_summary="Adults with biopsy-confirmed or clinically suspected inflammatory "
        "myopathy and elevated CK not explained by other causes.",
        location="Boston, MA",
    ),
    Trial(
        id="trial_pah_01",
        nct_id="NCT05010002",
        title="Novel Add-On Therapy for Refractory Pulmonary Arterial Hypertension",
        phase="Phase 3",
        condition="Pulmonary arterial hypertension",
        condition_keywords=["pulmonary", "dyspnea", "hypertension", "lung"],
        summary="Evaluating an add-on therapy for adults with pulmonary arterial hypertension "
        "and persistent symptoms despite standard background therapy.",
        eligibility_summary="Adults with WHO Group 1 PAH on stable background therapy with "
        "persistent exercise intolerance.",
        location="Boston, MA",
    ),
    Trial(
        id="trial_arrhythmia_01",
        nct_id="NCT05010003",
        title="Ablation Technique Comparison for Refractory Arrhythmia",
        phase="Phase 2",
        condition="Refractory cardiac arrhythmia",
        condition_keywords=["arrhythmia", "palpitation", "heart"],
        summary="Comparing two ablation techniques in patients with arrhythmia that hasn't "
        "responded to standard rhythm control.",
        eligibility_summary="Adults with a documented arrhythmia refractory to at least one "
        "prior rhythm-control attempt.",
        location="Cambridge, MA",
    ),
    Trial(
        id="trial_neuropathy_01",
        nct_id="NCT05010004",
        title="Genetic Screening Registry for Undiagnosed Peripheral Neuropathy",
        phase="Observational",
        condition="Undiagnosed peripheral neuropathy",
        condition_keywords=["neuropathy", "numbness", "tremor"],
        summary="A registry offering expanded genetic screening for patients with peripheral "
        "neuropathy that standard workup hasn't explained.",
        eligibility_summary="Adults with numbness, tingling, or tremor of unclear cause after a "
        "standard neurology workup.",
        location="Worcester, MA",
    ),
]


def trial_by_id(trial_id: str) -> Trial | None:
    return next((t for t in TRIALS if t.id == trial_id), None)
