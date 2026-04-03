from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config import get_settings

async_engine: Optional[AsyncEngine] = None
async_session: Optional[async_sessionmaker[AsyncSession]] = None


def init_db_session() -> None:
    global async_engine, async_session

    settings = get_settings()
    if settings.db is None:
        raise RuntimeError("Database config is not set for source control APIs.")

    db_config = settings.db.postgres
    database_url = (
        f"postgresql+asyncpg://{db_config.user}:{db_config.password}"
        f"@{db_config.host}:{db_config.port}/{db_config.database}"
    )

    async_engine = create_async_engine(database_url, echo=True)
    async_session = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    if async_session is None:
        raise RuntimeError("Database session not initialized. Call init_db_session() first.")
    return async_session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    session_factory = _get_session_factory()

    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
        finally:
            await session.close()

# for Depneds injection in FastAPI
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session_scope() as session:
        yield session
