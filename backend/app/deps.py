"""FastAPI dependencies and the builders the Celery worker reuses."""

import logging
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking import Booker
from app.config import settings
from app.db.repository import Repository
from app.db.session import SessionFactory, default_session_factory, get_session
from app.matching.claude_analyzer import ClaudeAnalyzer
from app.matching.rules_analyzer import RulesAnalyzer
from app.matching.service import Analyzers
from app.matching.types import CandidateProvider
from app.seed.fixtures import FixtureCandidateProvider

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


def build_candidate_provider() -> CandidateProvider:
    # PLACEHOLDER: hand-typed fixtures until Member 3's distance/insurance/scheduling exist.
    return FixtureCandidateProvider()


@lru_cache
def get_analyzers() -> Analyzers:
    return build_analyzers()


def get_candidate_provider() -> CandidateProvider:
    return build_candidate_provider()


def get_session_factory() -> SessionFactory:
    return default_session_factory()


def get_booker() -> Booker | None:
    """None until Member 3's booking is wired in; override this dependency to plug it in."""
    return None


def get_repo(session: AsyncSession = Depends(get_session)) -> Repository:
    return Repository(session)
