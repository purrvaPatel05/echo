"""Referral lifecycle. Every state change past `matched` needs an explicit physician action.

Parsing and matching are background jobs: the POST returns 202 and the client polls the GET.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app import jobs
from app.booking import Booker
from app.db.repository import Repository
from app.db.session import SessionFactory
from app.deps import (
    get_analyzers,
    get_booker,
    get_candidate_provider,
    get_repo,
    get_session_factory,
)
from app.matching.service import Analyzers
from app.matching.types import CandidateProvider
from app.models.match import MatchRun
from app.models.referral import (
    ApproveRequest,
    PatientSummary,
    Referral,
    ReferralCreate,
    ReferralUpdate,
)
from app.services import referrals as svc

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.post("", response_model=Referral, status_code=201)
async def create_referral(body: ReferralCreate, repo: Repository = Depends(get_repo)):
    if await repo.patient(body.patient_id) is None:
        raise HTTPException(404, "Patient not found")
    if await repo.physician(body.referring_physician_id) is None:
        raise HTTPException(404, "Referring physician not found")
    return await repo.create_referral(body)


@router.get("", response_model=list[Referral])
async def list_referrals(repo: Repository = Depends(get_repo)):
    return await repo.referrals()


@router.get("/{referral_id}", response_model=Referral)
async def get_referral(referral_id: str, repo: Repository = Depends(get_repo)):
    return await svc.get_or_404(repo, referral_id)


@router.patch("/{referral_id}", response_model=Referral)
async def confirm_referral(
    referral_id: str, body: ReferralUpdate, repo: Repository = Depends(get_repo)
):
    """Physician confirms or overrides urgency and complexity."""
    ref = await svc.get_or_404(repo, referral_id)
    return await svc.confirm(repo, ref, body.urgency, body.complexity)


@router.post("/{referral_id}/parse", response_model=Referral, status_code=202)
async def parse_referral(
    referral_id: str,
    background: BackgroundTasks,
    repo: Repository = Depends(get_repo),
    session_factory: SessionFactory = Depends(get_session_factory),
    analyzers: Analyzers = Depends(get_analyzers),
):
    """Queue case parsing. Poll GET /referrals/{id} until `parsed_case` is set."""
    ref = await svc.get_or_404(repo, referral_id)
    jobs.enqueue_parse(background, referral_id, session_factory, analyzers)
    return ref


@router.post(
    "/{referral_id}/match",
    response_model=MatchRun,
    status_code=202,
    responses={
        409: {"description": "Not parsed, or complexity not yet confirmed by the physician"}
    },
)
async def start_match(
    referral_id: str,
    background: BackgroundTasks,
    repo: Repository = Depends(get_repo),
    session_factory: SessionFactory = Depends(get_session_factory),
    analyzers: Analyzers = Depends(get_analyzers),
    provider: CandidateProvider = Depends(get_candidate_provider),
):
    ref = await svc.get_or_404(repo, referral_id)
    svc.require_matchable(ref)
    run = await repo.create_match_run(referral_id)
    jobs.enqueue_match(background, run.id, session_factory, analyzers, provider)
    return run


@router.get("/{referral_id}/match", response_model=MatchRun)
async def get_latest_match(referral_id: str, repo: Repository = Depends(get_repo)):
    """Latest match run for the referral; poll until status is complete or failed."""
    await svc.get_or_404(repo, referral_id)
    run = await repo.latest_match_run(referral_id)
    if run is None:
        raise HTTPException(404, "No match has been started for this referral")
    return run


@router.post(
    "/{referral_id}/approve",
    response_model=Referral,
    responses={
        403: {"description": "Approver is not the referring physician"},
        409: {"description": "Stale match run, or slot no longer available; re-run matching"},
    },
)
async def approve_and_book(
    referral_id: str,
    body: ApproveRequest,
    repo: Repository = Depends(get_repo),
    booker: Booker | None = Depends(get_booker),
):
    """The physician's explicit approval. This is the only path that approves or books."""
    return await svc.approve(repo, referral_id, body, booker)


@router.post("/{referral_id}/waitlist", response_model=Referral)
async def waitlist(referral_id: str, repo: Repository = Depends(get_repo)):
    return await svc.waitlist(repo, referral_id)


@router.get("/{referral_id}/patient-summary", response_model=PatientSummary)
async def patient_summary(referral_id: str, repo: Repository = Depends(get_repo)):
    ref = await svc.get_or_404(repo, referral_id)
    return await svc.patient_summary(repo, ref)
