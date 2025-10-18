import asyncio
import os
import random
import sys
from collections.abc import AsyncGenerator
from pathlib import Path

# Set DEV_MODE before any imports to disable rate limiting
os.environ["DEV_MODE"] = "true"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from sqlalchemy import select

from api.app import create_app
from api.dependencies import CurrentTenant, get_session
from database import crud
from database.models import Base, Tenant, User

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


@pytest.fixture
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
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
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with session_factory() as session:
        # Create default tenant without specifying id (use auto-increment)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        default_tenant = Tenant(name="Default Tenant", slug="default", is_active=True, created_at=now, updated_at=now)
        session.add(default_tenant)
        await session.flush()  # Get the auto-generated id
        
        # Store the default tenant id for use in fixtures
        session.info['default_tenant_id'] = default_tenant.id
        
        await session.commit()

        try:
            yield session
        finally:
            await session.rollback()


@pytest.fixture
async def app(db_session: AsyncSession):
    # DEV_MODE is already set at module level to disable rate limiting
    application = create_app()

    async def _override_session():
        yield db_session

    application.dependency_overrides[get_session] = _override_session

    # Disable rate limiting for tests by removing the limiter from state
    # This prevents slowapi from checking limits
    if hasattr(application.state, "limiter"):
        # Create a mock limiter that always allows requests
        class MockLimiter:
            enabled = False
            
            def _inject_headers(self, response, rate_limit):
                return response
            
            def limit(self, *args, **kwargs):
                # Return a decorator that does nothing
                def decorator(func):
                    return func
                return decorator
            
            def __call__(self, *args, **kwargs):
                # Make the limiter callable and return self for chaining
                return self
        
        application.state.limiter = MockLimiter()

    try:
        yield application
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


# --- Multi-tenancy Fixtures --- #

@pytest.fixture
async def current_tenant(tenant_1: Tenant) -> CurrentTenant:
    return CurrentTenant(tenant_id=tenant_1.id, is_super_admin=False, tenant=tenant_1)


@pytest.fixture
async def tenant_1(db_session: AsyncSession) -> Tenant:
    # Get the default tenant created in db_session fixture
    stmt = select(Tenant).where(Tenant.slug == "default")
    result = await db_session.execute(stmt)
    return result.scalar_one()


@pytest.fixture
async def tenant_2(db_session: AsyncSession) -> Tenant:
    tenant = Tenant(id=2, name="Second Tenant", slug="second", is_active=True)
    db_session.add(tenant)
    await db_session.commit()
    return tenant


@pytest.fixture
async def user_tenant_1(db_session: AsyncSession, tenant_1: Tenant) -> User:
    user = await crud.create_user(
        db_session,
        CurrentTenant(tenant_id=tenant_1.id, is_super_admin=False, tenant=tenant_1),
        telegram_id=random.randint(10000, 20000),
        display_name="User Tenant 1",
        role="teacher",
        tenant_id=tenant_1.id,
        username=f"user_t1_{random.randint(1, 1000)}",
    )
    await db_session.commit()
    return user


@pytest.fixture
async def user_tenant_2(db_session: AsyncSession, tenant_2: Tenant) -> User:
    user = await crud.create_user(
        db_session,
        CurrentTenant(tenant_id=tenant_2.id, is_super_admin=False, tenant=tenant_2),
        telegram_id=random.randint(20001, 30000),
        display_name="User Tenant 2",
        role="teacher",
        tenant_id=tenant_2.id,
        username=f"user_t2_{random.randint(1, 1000)}",
    )
    await db_session.commit()
    return user


@pytest.fixture
async def super_admin_user(db_session: AsyncSession) -> User:
    user = await crud.create_user(
        db_session,
        CurrentTenant(tenant_id=None, is_super_admin=True, tenant=None),
        telegram_id=random.randint(30001, 40000),
        display_name="Super Admin",
        role="admin",
        tenant_id=None,  # Global admin
        username=f"super_admin_{random.randint(1, 1000)}",
    )
    await db_session.commit()
    return user



# --- User Role Fixtures for Testing --- #

@pytest.fixture
async def teacher_user(db_session: AsyncSession, tenant_1: Tenant) -> User:
    """Create a teacher user for testing."""
    user = await crud.create_user(
        db_session,
        CurrentTenant(tenant_id=tenant_1.id, is_super_admin=False, tenant=tenant_1),
        telegram_id=random.randint(40001, 50000),
        display_name="Teacher User",
        role="teacher",
        tenant_id=tenant_1.id,
        username=f"teacher_{random.randint(1, 1000)}",
    )
    await db_session.commit()
    return user


@pytest.fixture
async def viewer_user(db_session: AsyncSession, tenant_1: Tenant) -> User:
    """Create a viewer (student) user for testing."""
    user = await crud.create_user(
        db_session,
        CurrentTenant(tenant_id=tenant_1.id, is_super_admin=False, tenant=tenant_1),
        telegram_id=random.randint(50001, 60000),
        display_name="Viewer User",
        role="viewer",
        tenant_id=tenant_1.id,
        username=f"viewer_{random.randint(1, 1000)}",
    )
    await db_session.commit()
    return user


@pytest.fixture
async def teacher_token(teacher_user: User) -> str:
    """Generate JWT token for teacher user."""
    from api.security import create_access_token
    
    token_payload = {
        "sub": str(teacher_user.id),
        "role": teacher_user.role,
        "telegram_id": teacher_user.telegram_id,
        "tenant_id": teacher_user.tenant_id,
    }
    return create_access_token(token_payload)


@pytest.fixture
async def viewer_token(viewer_user: User) -> str:
    """Generate JWT token for viewer user."""
    from api.security import create_access_token
    
    token_payload = {
        "sub": str(viewer_user.id),
        "role": viewer_user.role,
        "telegram_id": viewer_user.telegram_id,
        "tenant_id": viewer_user.tenant_id,
    }
    return create_access_token(token_payload)
