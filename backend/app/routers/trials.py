"""ClinicalTrials.gov (mocked). Matched trials are a discussion option, not sent to the patient
until the physician explicitly approves one (see services.referrals.approve_trial)."""

from fastapi import APIRouter, Depends

from app.auth import CurrentUser, current_user
from app.db.repository import Repository
from app.deps import get_repo
from app.models.referral import ApproveTrialRequest, Referral
from app.models.trials import Trial
from app.services import referrals as svc

router = APIRouter(prefix="/referrals/{referral_id}/trials", tags=["trials"])


@router.get(
    "",
    response_model=list[Trial],
    responses={409: {"description": "Not parsed, or complexity is not rare_complex"}},
)
async def list_trials(
    referral_id: str,
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(current_user),
):
    ref = await svc.get_or_404(repo, referral_id, user)
    return svc.matched_trials(ref)


@router.post(
    "/{trial_id}/approve",
    response_model=Referral,
    responses={
        403: {"description": "Approver is not the referring physician"},
        422: {"description": "Trial was not in the matched list for this case"},
    },
)
async def approve_trial(
    referral_id: str,
    trial_id: str,
    body: ApproveTrialRequest,
    repo: Repository = Depends(get_repo),
    user: CurrentUser = Depends(current_user),
):
    """The physician's explicit approval to discuss this trial with the patient."""
    return await svc.approve_trial(repo, referral_id, trial_id, body.approved_by, user)
