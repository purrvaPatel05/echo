"""`/api/echo/*`: the endpoints the ECHO frontend calls (see docs/echo-api-contract-changes.md).

Hidden from the OpenAPI schema on purpose: the committed openapi.json describes the core API,
and this layer's contract is that document.
"""

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.booking import Booker
from app.config import settings
from app.db.repository import Repository
from app.db.session import SessionFactory, get_session
from app.deps import (
    get_analyzers,
    get_booker,
    get_candidate_provider,
    get_redis,
    get_repo,
    get_session_factory,
)
from app.echo import schemas as s
from app.echo.auth import echo_user
from app.echo.pipeline import run_matching, run_pipeline, start_match_run
from app.echo.service import EchoService
from app.echo.session import LoginLimiter, demo_email, issue_token, limiter, password_matches
from app.echo.simulation import simulate_reply
from app.echo.store import EchoStore
from app.matching.service import Analyzers
from app.matching.types import CandidateProvider
from app.routers.consult import _publish

router = APIRouter(prefix="/api/echo", tags=["echo"], include_in_schema=False)


async def get_echo(
    repo: Repository = Depends(get_repo),
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(echo_user),
) -> EchoService:
    return EchoService(repo, EchoStore(session), user)


Echo = Depends(get_echo)


# ---- sign-in (AUTH_MODE=session): the only /api/echo routes that need no login --------------

_ip_limiter = LoginLimiter(limit=30, window=60.0)


def _session_mode() -> bool:
    return settings.auth_mode == "session"


def _physician_out(p) -> s.Physician:
    return s.Physician(id=p.id, name=p.name, specialty=p.specialty, organization=p.practice_name)


@router.get("/auth/config", response_model=s.AuthConfig)
async def auth_config():
    """Tells the frontend whether to show the login page. Open to everyone."""
    return s.AuthConfig(
        login=_session_mode(), demo_accounts=_session_mode() and settings.demo_account_login
    )


@router.get("/auth/demo-accounts", response_model=list[s.DemoAccount])
async def demo_accounts(repo: Repository = Depends(get_repo)):
    if not (_session_mode() and settings.demo_account_login):
        raise HTTPException(404, "Not found")
    return [
        s.DemoAccount(
            id=p.id,
            name=p.name,
            specialty=p.specialty,
            organization=p.practice_name,
            email=demo_email(p),
        )
        for p in await repo.physicians()
    ]


@router.post("/auth/login", response_model=s.Session)
async def login(body: s.LoginInput, request: Request, repo: Repository = Depends(get_repo)):
    """Email + the demo password. The same answer for an unknown email and a wrong password."""
    if not _session_mode():
        raise HTTPException(404, "Not found")
    email = body.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}|{email}"
    if limiter.blocked(key) or _ip_limiter.blocked(ip):
        raise HTTPException(429, "Too many attempts. Try again in a minute.")
    match = next((p for p in await repo.physicians() if demo_email(p) == email), None)
    password_ok = password_matches(
        body.password
    )  # always checked, so timing doesn't reveal the email
    if match is None or not password_ok:
        limiter.record_failure(key)
        _ip_limiter.record_failure(ip)
        raise HTTPException(401, "Check your email and password.")
    limiter.clear(key)
    return s.Session(token=issue_token(match.id), physician=_physician_out(match))


@router.post("/auth/demo-login", response_model=s.Session)
async def demo_login(body: s.DemoLoginInput, repo: Repository = Depends(get_repo)):
    """One-click sign-in as a demo physician (DEMO_ACCOUNT_LOGIN=true only)."""
    if not (_session_mode() and settings.demo_account_login):
        raise HTTPException(404, "Not found")
    physician = await repo.physician(body.physician_id)
    if physician is None:
        raise HTTPException(404, "Not found")
    return s.Session(token=issue_token(physician.id), physician=_physician_out(physician))


@router.get("/me", response_model=s.Physician)
async def me(svc: EchoService = Echo):
    return await svc.me()


@router.get("/patients", response_model=list[s.Patient])
async def patients(svc: EchoService = Echo):
    return await svc.patients()


@router.get("/referral-options", response_model=s.ReferralOptions)
async def referral_options(svc: EchoService = Echo):
    return await svc.referral_options()


@router.get("/colleagues", response_model=list[s.Colleague])
async def colleagues(svc: EchoService = Echo):
    return await svc.colleagues()


# ---- referrals ------------------------------------------------------------------------------


@router.get("/referrals", response_model=list[s.Referral])
async def list_referrals(svc: EchoService = Echo):
    return await svc.referrals()


@router.post("/referrals", response_model=s.Referral, status_code=201)
async def create_referral(
    body: s.NewReferralInput,
    background: BackgroundTasks,
    svc: EchoService = Echo,
    session_factory: SessionFactory = Depends(get_session_factory),
    analyzers: Analyzers = Depends(get_analyzers),
    provider: CandidateProvider = Depends(get_candidate_provider),
):
    """Saves the referral first (it shows on the dashboard right away), then analyzes it in the
    background. Nothing is booked: booking needs the physician's explicit approval."""
    ref = await svc.create_referral(body)
    background.add_task(run_pipeline, ref.id, session_factory, analyzers, provider)
    return await svc.referral(ref.id)


@router.get("/referrals/{referral_id}", response_model=s.Referral)
async def get_referral(referral_id: str, svc: EchoService = Echo):
    return await svc.referral(referral_id)


@router.post("/referrals/{referral_id}/select", response_model=s.Referral)
async def select_specialist(referral_id: str, body: s.SelectInput, svc: EchoService = Echo):
    return await svc.select(referral_id, body.specialist_id)


@router.get("/referrals/{referral_id}/analysis", response_model=s.Analysis)
async def analysis(referral_id: str, svc: EchoService = Echo):
    return await svc.analysis(referral_id)


@router.post("/referrals/{referral_id}/analysis/retry", response_model=s.Analysis)
async def retry_analysis(
    referral_id: str,
    background: BackgroundTasks,
    svc: EchoService = Echo,
    session_factory: SessionFactory = Depends(get_session_factory),
    analyzers: Analyzers = Depends(get_analyzers),
    provider: CandidateProvider = Depends(get_candidate_provider),
):
    b = await svc.prepare_retry(referral_id)
    if b.ref.parsed_case is None:  # the case never parsed: start over from the parse
        background.add_task(run_pipeline, referral_id, session_factory, analyzers, provider)
    else:  # only matching failed: queue a fresh run now, so the snapshot below shows it running
        run_id = await start_match_run(referral_id, session_factory)
        background.add_task(run_matching, run_id, referral_id, session_factory, analyzers, provider)
    return await svc.analysis(referral_id)


_analysis_locks: dict[str, asyncio.Lock] = {}


@router.get("/referrals/{referral_id}/matches", response_model=s.MatchesResult)
async def matches(
    referral_id: str,
    distance_miles: int | None = Query(None, alias="distanceMiles", gt=0),
    include_partial: bool = Query(False, alias="includePartial"),
    svc: EchoService = Echo,
    session_factory: SessionFactory = Depends(get_session_factory),
    analyzers: Analyzers = Depends(get_analyzers),
    provider: CandidateProvider = Depends(get_candidate_provider),
):
    """The ranked matches. A referral nobody has analyzed yet (or whose analysis failed) is analyzed
    right here, so opening its matches works instead of failing until someone retries."""
    if await svc.needs_analysis(referral_id):
        lock = _analysis_locks.setdefault(referral_id, asyncio.Lock())
        async with lock:  # two requests for one referral analyze it once
            if await svc.needs_analysis(referral_id):
                await svc.mark_analysis_started(referral_id)
                await run_pipeline(referral_id, session_factory, analyzers, provider)
    return await svc.matches(referral_id, distance_miles, include_partial)


@router.get("/specialists/{specialist_id}/slots", response_model=list[s.Slot])
async def slots(specialist_id: str, svc: EchoService = Echo):
    return await svc.slots(specialist_id)


@router.post("/referrals/{referral_id}/approve", response_model=s.Referral)
async def approve(
    referral_id: str,
    body: s.ApproveInput,
    svc: EchoService = Echo,
    booker: Booker = Depends(get_booker),
):
    """The physician's explicit approval: the only call here that books an appointment."""
    return await svc.approve(referral_id, body, booker)


@router.post("/referrals/{referral_id}/patient-response", response_model=s.Referral)
async def patient_response(referral_id: str, body: s.PatientResponseInput, svc: EchoService = Echo):
    """Demo modes only: record the patient's answer; nothing else can yet."""
    if settings.auth_mode not in ("dev", "demo", "session"):  # all synthetic-data demo modes
        raise HTTPException(404, "Not found")
    return await svc.patient_response(referral_id, body.status)


# ---- consult ---------------------------------------------------------------------------------


@router.get("/consults", response_model=list[s.ConsultSummary])
async def consults(svc: EchoService = Echo):
    """My conversations (started by me or by a colleague), newest activity first."""
    return await svc.consult_threads()


@router.post("/consults", response_model=s.ConsultThread, status_code=201)
async def start_consult(
    body: s.StartConsultInput,
    background: BackgroundTasks,
    svc: EchoService = Echo,
    redis_client=Depends(get_redis),
    session_factory: SessionFactory = Depends(get_session_factory),
):
    """Starts a conversation (the physician's explicit action). A referral is optional. The message
    is saved first; live delivery to the colleague's socket is best effort."""
    thread, message = await svc.start_consult(body)
    await _publish(redis_client, body.colleague_id, message)
    _maybe_simulate(background, session_factory, thread.id, body.colleague_id)
    return thread


@router.get("/consults/{thread_id}", response_model=s.ConsultThread)
async def get_consult(thread_id: str, svc: EchoService = Echo):
    return await svc.consult_thread(thread_id)


@router.post("/consults/{thread_id}/messages", response_model=s.ConsultThread, status_code=201)
async def send_consult_message(
    thread_id: str,
    body: s.SendMessageInput,
    background: BackgroundTasks,
    svc: EchoService = Echo,
    redis_client=Depends(get_redis),
    session_factory: SessionFactory = Depends(get_session_factory),
):
    thread, message = await svc.send_consult_message(thread_id, body.text)
    await _publish(redis_client, thread.colleague.id, message)
    _maybe_simulate(background, session_factory, thread.id, thread.colleague.id)
    return thread


def _maybe_simulate(
    background: BackgroundTasks, session_factory, thread_id: str, colleague_id: str
):
    """Demo only (SIMULATE_COLLEAGUE_REPLIES): the colleague answers a few seconds later."""
    if settings.simulate_colleague_replies:
        background.add_task(
            simulate_reply,
            thread_id,
            colleague_id,
            session_factory,
            settings.simulated_reply_delay_seconds,
        )


# ---- clinical trials -------------------------------------------------------------------------


@router.get("/referrals/{referral_id}/trials/criteria", response_model=s.TrialCriteria)
async def trial_criteria(
    referral_id: str,
    distance_miles: str | None = Query(None, alias="distanceMiles"),
    all_statuses: bool = Query(False, alias="allStatuses"),
    svc: EchoService = Echo,
):
    return await svc.trial_criteria(referral_id, distance_miles, all_statuses)


@router.get("/referrals/{referral_id}/trials", response_model=s.TrialsResult)
async def trials(
    referral_id: str,
    distance_miles: str | None = Query(None, alias="distanceMiles"),
    all_statuses: bool = Query(False, alias="allStatuses"),
    svc: EchoService = Echo,
):
    return await svc.trials(referral_id, distance_miles, all_statuses)
