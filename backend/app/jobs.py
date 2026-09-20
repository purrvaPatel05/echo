"""Background jobs: case parsing and matching.

Each job opens its own session and re-reads the referral before writing, so a physician's
edit made while Claude was thinking isn't overwritten.
"""

import logging
from datetime import UTC, datetime

from fastapi import BackgroundTasks

from app.config import settings
from app.db.repository import Repository
from app.db.session import SessionFactory
from app.matching import service
from app.matching.service import Analyzers
from app.matching.types import CandidateProvider
from app.models.enums import JobStatus, ReferralStatus

logger = logging.getLogger(__name__)


async def run_parse(referral_id: str, session_factory: SessionFactory, analyzers: Analyzers):
    async with session_factory() as session:
        repo = Repository(session)
        ref = await repo.referral(referral_id)
        if ref is None:
            return
        specialties = sorted({s.specialty for s in await repo.specialists()})
        parsed = await service.parse_case(analyzers, ref.case_notes, ref.urgency, specialties)
        ref = await repo.referral(referral_id)  # re-read: the physician may have edited it
        ref.parsed_case = parsed
        await repo.save_referral(ref)


async def run_match(
    run_id: str,
    session_factory: SessionFactory,
    analyzers: Analyzers,
    provider: CandidateProvider,
):
    async with session_factory() as session:
        repo = Repository(session)
        run = await repo.match_run(run_id)
        if run is None:
            return
        run.status = JobStatus.RUNNING
        await repo.save_match_run(run)
        try:
            ref = await repo.referral(run.referral_id)
            patient = await repo.patient(ref.patient_id)
            candidates = await provider.candidates_for(patient, await repo.specialists())
            out = await service.match(
                analyzers, ref.parsed_case, candidates, ref.urgency, ref.complexity
            )
            run.status = JobStatus.COMPLETE
            run.weight_profile = out.outcome.weight_profile
            run.degraded = out.degraded
            run.results = out.outcome.results
            run.too_late = out.outcome.too_late
            run.completed_at = datetime.now(UTC)
            await repo.save_match_run(run)
            ref = await repo.referral(run.referral_id)
            if ref.status in (ReferralStatus.DRAFT, ReferralStatus.WAITLISTED):
                ref.status = ReferralStatus.MATCHED
                await repo.save_referral(ref)
        except Exception:
            logger.exception("Match run %s failed", run_id)
            run.status = JobStatus.FAILED
            run.error = "Matching failed; see server logs"
            run.completed_at = datetime.now(UTC)
            await repo.save_match_run(run)


def enqueue_parse(
    background: BackgroundTasks,
    referral_id: str,
    session_factory: SessionFactory,
    analyzers: Analyzers,
) -> None:
    if settings.job_backend == "celery":
        from app.celery_app import parse_referral_task

        parse_referral_task.delay(referral_id)
    else:
        background.add_task(run_parse, referral_id, session_factory, analyzers)


def enqueue_match(
    background: BackgroundTasks,
    run_id: str,
    session_factory: SessionFactory,
    analyzers: Analyzers,
    provider: CandidateProvider,
) -> None:
    if settings.job_backend == "celery":
        from app.celery_app import match_referral_task

        match_referral_task.delay(run_id)
    else:
        background.add_task(run_match, run_id, session_factory, analyzers, provider)
