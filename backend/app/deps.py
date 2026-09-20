"""FastAPI dependencies and the builders the Celery worker reuses."""

import logging
from functools import lru_cache

import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking import Booker
from app.candidates import RealCandidateProvider
from app.config import settings
from app.db.repository import Repository
from app.db.session import SessionFactory, default_session_factory, get_session
from app.integrations.maps import DistanceClient
from app.matching.claude_analyzer import ClaudeAnalyzer
from app.matching.rules_analyzer import RulesAnalyzer
from app.matching.service import Analyzers
from app.matching.types import CandidateProvider
from app.scheduling.booker import DbBooker

logger = logging.getLogger(__name__)


def build_analyzers() -> Analyzers:
    """Claude when ANTHROPIC_API_KEY is set; otherwise rules-only (matches come back flagged)."""
    primary = None
    if settings.anthropic_api_key:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.claude_timeout_seconds,
            max_retries=1,
        )
        primary = ClaudeAnalyzer(
            client, settings.claude_model, server_fallback=settings.claude_server_fallback
        )
    else:
        logger.warning("ANTHROPIC_API_KEY not set: matching runs rules-only (degraded)")
    return Analyzers(primary=primary, fallback=RulesAnalyzer())


def build_candidate_provider(session_factory: SessionFactory | None = None) -> CandidateProvider:
    """Distance (Google Maps, or haversine when GOOGLE_MAPS_API_KEY is unset/fails), insurance
    network status, and earliest open slot -- each backed by the tables in app.db.models.

    `session_factory` defaults to the shared pooled factory (the FastAPI/inline-jobs path);
    Celery passes its own per-task NullPool factory explicitly, matching how it already handles
    `run_match`'s session (see app/celery_app.py).
    """
    factory = session_factory or get_session_factory()
    distance_client = DistanceClient(settings.google_maps_api_key)
    return RealCandidateProvider(factory, distance_client)


@lru_cache
def get_analyzers() -> Analyzers:
    return build_analyzers()


@lru_cache
def get_candidate_provider() -> CandidateProvider:
    return build_candidate_provider()


def get_session_factory() -> SessionFactory:
    return default_session_factory()


def get_booker() -> Booker:
    return DbBooker(get_session_factory())


def get_repo(session: AsyncSession = Depends(get_session)) -> Repository:
    return Repository(session)


@lru_cache
def get_redis() -> redis.Redis:
    """Shared client for the peer-consult WebSocket's pub/sub relay (app.routers.consult)."""
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)
