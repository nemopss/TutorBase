import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from httpx import AsyncClient, ASGITransport

from api.app import create_app
from api.dependencies import get_session

from database.models import Base

TEST_DB_ENV_VAR = "TEST_DATABASE_URL"


def _get_database_url() -> str:
    url_str = os.getenv(TEST_DB_ENV_VAR, "postgresql+asyncpg://app:app@localhost:5432/app_test")
    if not url_str:
        raise RuntimeError(
            f"{TEST_DB_ENV_VAR} is not set. Example: "
            "'postgresql+asyncpg://app:app@localhost:5432/app_test'"
        )
    url = make_url(url_str)
    if url.drivername.startswith("postgresql") and (
        not url.database or not url.database.endswith("_test")
    ):
        raise RuntimeError(
            "Test database name must end with '_test' to avoid accidental data loss."
        )
    return url_str


# @pytest.fixture(scope="session")
# def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
#     """Reuse a single event loop for the whole test session."""
#     loop = asyncio.new_event_loop()
#     asyncio.set_event_loop(loop)
#     try:
#         yield loop
#     finally:
#         loop.close()


@pytest.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create a fresh database schema for each test."""
    database_url = _get_database_url()
    engine = create_async_engine(database_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession bound to the per-test engine."""
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture
async def app(db_session: AsyncSession):
    """Provide FastAPI app with test overrides."""
    application = create_app()

    async def _override_session():
        yield db_session

    application.dependency_overrides[get_session] = _override_session

    limiter = getattr(application.state, "limiter", None)
    if limiter is not None:
        setattr(limiter, "enabled", False)

    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    """HTTPX async client bound to FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client
