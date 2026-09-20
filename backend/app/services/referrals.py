"""Referral business rules. Raises HTTPException directly to keep the hackathon code compact."""

from datetime import UTC, datetime

from fastapi import HTTPException

from app.auth import CurrentUser, require_same_physician
from app.booking import Booker, SlotUnavailableError
from app.db.repository import Repository
from app.models.enums import (
    Complexity,
    InsuranceStatus,
    JobStatus,
    ReferralStatus,
    Urgency,
)
from app.models.match import MatchResult
from app.models.referral import (
    Approval,
    ApproveRequest,
    PatientSummary,
    Referral,
)
from app.models.trials import Trial, TrialApproval
from app.trials.data import trial_by_id
from app.trials.matcher import match_trials

_EDITABLE = (ReferralStatus.DRAFT, ReferralStatus.MATCHED, ReferralStatus.WAITLISTED)


async def get_or_404(repo: Repository, referral_id: str, user: CurrentUser) -> Referral:
    """Physicians see only their own referrals; an admin sees all. Someone else's referral
    is reported as not found so its existence isn't revealed."""
    ref = await repo.referral(referral_id)
    if ref is None or (not user.is_admin and ref.referring_physician_id != user.physician_id):
        raise HTTPException(404, "Referral not found")
    return ref


def require_owner(ref: Referral, user: CurrentUser) -> None:
    """Approvals are the referring physician's alone, even for an admin."""
    if ref.referring_physician_id != user.physician_id:
        raise HTTPException(403, "Only the referring physician can approve this referral")


async def confirm(
    repo: Repository, ref: Referral, urgency: Urgency | None, complexity: Complexity | None
) -> Referral:
    """Physician confirms or overrides urgency/complexity. Changing either invalidates any
    existing match, so a matched referral drops back to draft and must be re-matched."""
    if ref.status not in _EDITABLE:
        raise HTTPException(409, f"Referral is {ref.status.value} and can no longer be edited")
    changed = (urgency is not None and urgency != ref.urgency) or (
        complexity is not None and complexity != ref.complexity
    )
    if urgency is not None:
        ref.urgency = urgency
    if complexity is not None:
        ref.complexity = complexity
    if changed and ref.status == ReferralStatus.MATCHED:
        ref.status = ReferralStatus.DRAFT
    return await repo.save_referral(ref)


def require_matchable(ref: Referral) -> None:
    if ref.status not in _EDITABLE:
        raise HTTPException(409, f"Referral is {ref.status.value}; it cannot be matched again")
    if ref.parsed_case is None:
        raise HTTPException(409, "Case has not been parsed yet")
    if ref.complexity is None:
        raise HTTPException(409, "Physician must confirm urgency and complexity before matching")


async def approve(
    repo: Repository,
    referral_id: str,
    body: ApproveRequest,
    booker: Booker | None,
    user: CurrentUser,
) -> Referral:
    """The only path that approves (and, if a booker is wired in, books) a referral."""
    ref = await get_or_404(repo, referral_id, user)
    require_same_physician(body.approved_by, user, "approved_by")
    require_owner(ref, user)
    if ref.status != ReferralStatus.MATCHED:
        raise HTTPException(409, f"Referral is {ref.status.value}; only matched referrals approve")
    run = await repo.latest_match_run(referral_id)
    if run is None or run.id != body.match_run_id:
        raise HTTPException(409, "Match run is unknown or stale; re-run matching")
    if run.status != JobStatus.COMPLETE:
        raise HTTPException(409, "Match run has not completed")
    result = next((r for r in run.results if r.specialist.id == body.specialist_id), None)
    if result is None:
        raise HTTPException(422, "Specialist was not in the match results")
    if result.earliest_slot is None or result.earliest_slot.id != body.slot_id:
        raise HTTPException(422, "Slot is not the one offered in the match results")

    appointment = None
    if booker is not None:
        try:
            appointment = await booker.book(ref, body.specialist_id, body.slot_id)
        except SlotUnavailableError:
            raise HTTPException(409, "That slot is no longer available; re-run matching") from None

    ref.approval = Approval(
        specialist_id=body.specialist_id,
        slot_id=body.slot_id,
        approved_by=user.physician_id,
        approved_at=datetime.now(UTC),
    )
    ref.appointment = appointment
    ref.status = ReferralStatus.BOOKED if appointment else ReferralStatus.APPROVED
    return await repo.save_referral(ref)


async def waitlist(repo: Repository, referral_id: str, user: CurrentUser) -> Referral:
    ref = await get_or_404(repo, referral_id, user)
    if ref.status != ReferralStatus.MATCHED:
        raise HTTPException(409, f"Referral is {ref.status.value}; only matched referrals waitlist")
    ref.status = ReferralStatus.WAITLISTED
    return await repo.save_referral(ref)


def matched_trials(ref: Referral) -> list[Trial]:
    """Trials the physician can discuss with the patient -- surfaced, never sent, until
    `approve_trial` records an explicit sign-off. Only meaningful once complexity is confirmed
    as rare/complex (CLAUDE.md: complexity "triggers trial lookup")."""
    if ref.parsed_case is None:
        raise HTTPException(409, "Case has not been parsed yet")
    if ref.complexity != Complexity.RARE_COMPLEX:
        raise HTTPException(409, "Trial lookup only applies when complexity is rare_complex")
    return match_trials(ref.parsed_case)


async def approve_trial(
    repo: Repository,
    referral_id: str,
    trial_id: str,
    approved_by: str | None,
    user: CurrentUser,
) -> Referral:
    """The physician's explicit approval to discuss this trial with the patient. Independent of
    specialist approval/booking -- a trial is a discussion option alongside the referral, not a
    replacement for it."""
    ref = await get_or_404(repo, referral_id, user)
    require_same_physician(approved_by, user, "approved_by")
    require_owner(ref, user)
    if trial_id not in {t.id for t in matched_trials(ref)}:
        raise HTTPException(422, "Trial was not in the matched list for this case")
    ref.trial_approval = TrialApproval(
        trial_id=trial_id, approved_by=user.physician_id, approved_at=datetime.now(UTC)
    )
    return await repo.save_referral(ref)


def _cost_note(result: MatchResult | None) -> str | None:
    if result is None:
        return None
    return {
        InsuranceStatus.OUT_OF_NETWORK: (
            "This specialist is out-of-network for your plan, so you may pay more than usual. "
            "Your insurer can tell you the expected cost."
        ),
        InsuranceStatus.UNVERIFIED: (
            "We couldn't confirm your coverage with this specialist. "
            "Please check with your insurance plan before the visit."
        ),
    }.get(result.insurance.status)


def _trial_note(ref: Referral) -> str | None:
    if ref.trial_approval is None:
        return None
    trial = trial_by_id(ref.trial_approval.trial_id)
    if trial is None:
        return None
    return (
        f'Your doctor has flagged a clinical trial that may be relevant: "{trial.title}" '
        f"({trial.phase}, {trial.location}). {trial.eligibility_summary} "
        "Ask your doctor if you'd like to learn more or discuss enrolling."
    )


async def patient_summary(repo: Repository, ref: Referral) -> PatientSummary:
    if ref.approval is None:
        return PatientSummary(
            referral_id=ref.id,
            summary="Your doctor is reviewing specialist options for you and will confirm "
            "your referral shortly.",
        )
    specialist = await repo.specialist(ref.approval.specialist_id)
    run = await repo.latest_match_run(ref.id)
    result = None
    if run is not None:
        result = next((r for r in run.results if r.specialist.id == specialist.id), None)
    reason = ref.parsed_case.condition_summary if ref.parsed_case else "the concerns in your case"
    text = (
        f"Your doctor has referred you to {specialist.name}, a specialist in "
        f"{specialist.specialty} at {specialist.practice_name}, because of: {reason.rstrip('.')}."
    )
    if ref.appointment is not None:
        text += f" Your appointment is on {ref.appointment.slot.start:%A, %B %d at %I:%M %p} UTC."
    else:
        text += " Your appointment is being scheduled."
    return PatientSummary(
        referral_id=ref.id,
        summary=text,
        specialist_name=specialist.name,
        appointment=ref.appointment,
        cost_note=_cost_note(result),
        trial_note=_trial_note(ref),
    )
