from collections.abc import AsyncIterator, Callable
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

SessionFactory = Callable[[], AsyncSession]


def make_session_factory(**engine_kwargs) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True, **engine_kwargs)
    return async_sessionmaker(engine, expire_on_commit=False)


@lru_cache
def default_session_factory() -> async_sessionmaker[AsyncSession]:
    return make_session_factory()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with default_session_factory()() as session:
        yield session
