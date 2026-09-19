"""Celery worker entrypoint: `celery -A app.celery_app worker` (set JOB_BACKEND=celery on the API).

Each task builds fresh clients and a NullPool engine because `asyncio.run` gives every task its
own event loop, and pooled connections / HTTP clients can't be shared across loops.
"""

import asyncio

from celery import Celery
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db.session import make_session_factory
from app.deps import build_analyzers, build_candidate_provider
from app.jobs import run_match, run_parse

celery_app = Celery("echo", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task(name="echo.parse_referral")
def parse_referral_task(referral_id: str) -> None:
    asyncio.run(run_parse(referral_id, make_session_factory(poolclass=NullPool), build_analyzers()))


@celery_app.task(name="echo.match_referral")
def match_referral_task(run_id: str) -> None:
    asyncio.run(
        run_match(
            run_id,
            make_session_factory(poolclass=NullPool),
            build_analyzers(),
            build_candidate_provider(),
        )
    )
