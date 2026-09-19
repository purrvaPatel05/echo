from dataclasses import dataclass
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.booking import Booker
from app.db.models import Base
from app.db.session import get_session
from app.deps import get_analyzers, get_booker, get_candidate_provider, get_session_factory
from app.main import app
from app.matching.rules_analyzer import RulesAnalyzer
from app.matching.service import Analyzers
from app.seed.__main__ import seed
from app.seed.fixtures import FixtureCandidateProvider


@dataclass
class Api:
    client: AsyncClient
    factory: async_sessionmaker
    state: dict


@pytest.fixture
async def api():
    """The real app on an in-memory SQLite database seeded with the demo data.

    Defaults to rules-only analysis (no Claude) and no booker; tests override via `api.state`.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await seed(session)

    state: dict = {
        "analyzers": Analyzers(primary=None, fallback=RulesAnalyzer()),
        "provider": FixtureCandidateProvider(today=date(2026, 9, 21)),
        "booker": None,
    }

    async def session_override():
        async with factory() as session:
            yield session

    app.dependency_overrides.update(
        {
            get_session: session_override,
            get_session_factory: lambda: factory,
            get_analyzers: lambda: state["analyzers"],
            get_candidate_provider: lambda: state["provider"],
            get_booker: lambda: state["booker"],
        }
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield Api(client, factory, state)
    app.dependency_overrides.clear()
    await engine.dispose()


__all__ = ["Api", "Booker"]
