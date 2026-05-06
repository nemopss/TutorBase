"""Tests for user registration endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from api.dependencies import CurrentTenant
from config import config
from database import crud
from database.models import InviteToken, Learner, LearnerAccountLink, LegalAcceptance, Tenant, TenantAccess, TenantSubscription, User
from tests import factories
from tests.api.utils import get_auth_headers


@pytest.mark.asyncio
async def test_register_tutor_success(client: AsyncClient, db_session: AsyncSession):
    """Test successful tutor registration."""
    registration_data = {
        "school_name": "Test Tutoring School",
        "tutor_name": "John Doe",
        "email": "john@example.com",
        "password": "password123",
        "offer_accepted": True,
        "privacy_accepted": True,
    }
    
    # Mock Telegram init data
    headers = {"X-Telegram-Init-Data": "dev"}
    
    response = await client.post("/api/v1/auth/register-tutor", json=registration_data, headers=headers)
    
    if response.status_code != 200:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.json()}")
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data
    assert "tenant" in data
    assert "message" in data
    
    # Check user data
    user_data = data["user"]
    assert user_data["role"] == "teacher"
    assert user_data["display_name"] == "John Doe"
    assert user_data["email"] == "john@example.com"
    
    # Check tenant data
    tenant_data = data["tenant"]
    assert tenant_data["name"] == "Test Tutoring School"
    assert "slug" in tenant_data

    access = (
        await db_session.execute(
            select(TenantAccess).where(TenantAccess.tenant_id == tenant_data["id"])
        )
    ).scalar_one()
    assert access.status == "lifetime"
    assert access.access_until is None
    assert access.grace_until is None

    subscription = (
        await db_session.execute(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_data["id"])
        )
    ).scalar_one()
    assert subscription.plan_code == "start"
    assert subscription.current_period_end is None

    acceptance = (
        await db_session.execute(
            select(LegalAcceptance).where(LegalAcceptance.user_id == user_data["id"])
        )
    ).scalar_one()
    assert acceptance.offer_version == "2026-04-29"
    assert acceptance.privacy_version == "2026-04-29"

    user = (
        await db_session.execute(
            select(User).where(User.id == user_data["id"])
        )
    ).scalar_one()
    assert user.email_normalized == "john@example.com"
    assert user.password_hash
    assert user.password_hash != "password123"


@pytest.mark.asyncio
async def test_register_student_success(client: AsyncClient, db_session: AsyncSession, tenant_1: Tenant):
    """Test successful student registration with valid invite."""
    # Create teacher and invite token
    teacher = await factories.create_user(db_session, role="teacher", tenant_id=tenant_1.id)
    await db_session.flush()  # Get teacher.id
    invite_token = await factories.create_invite_token(db_session, tenant_id=tenant_1.id, created_by_user_id=teacher.id)
    await db_session.commit()
    
    registration_data = {
        "invite_token": invite_token.token,
        "student_name": "Jane Student",
        "offer_accepted": True,
        "privacy_accepted": True,
    }
    
    headers = {"X-Telegram-Init-Data": "dev"}
    
    response = await client.post("/api/v1/auth/register-student", json=registration_data, headers=headers)
    
    assert response.status_code == 200
    data = response.json()
    
    # Check response structure
    assert "access_token" in data
    assert "user" in data
    assert "tenant" in data
    
    # Check user data
    user_data = data["user"]
    assert user_data["role"] == "viewer"
    assert user_data["display_name"] == "Jane Student"

    await db_session.refresh(invite_token)
    assert invite_token.used_at is not None


@pytest.mark.asyncio
async def test_register_student_personal_invite_links_existing_learner(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
    monkeypatch,
):
    monkeypatch.setattr(config, "DEV_MODE", True)
    monkeypatch.setattr(config, "DEV_INIT_DATA", "dev")
    monkeypatch.setattr(config, "DEV_TELEGRAM_ID", 223344)
    monkeypatch.setattr(config, "DEV_USERNAME", "personal_student")
    monkeypatch.setattr(config, "DEV_DISPLAY_NAME", "Telegram Student")

    teacher = await factories.create_user(db_session, role="teacher", tenant_id=tenant_1.id)
    await db_session.flush()
    learner = Learner(
        tenant_id=tenant_1.id,
        bot_user_id=None,
        display_name="Teacher Named Learner",
        notes="Created before registration",
        notifications_enabled=False,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(learner)
    await db_session.flush()
    invite_token = await factories.create_invite_token(
        db_session,
        tenant_id=tenant_1.id,
        learner_id=learner.id,
        created_by_user_id=teacher.id,
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register-student",
        json={
            "invite_token": invite_token.token,
            "student_name": "Student Own Name",
            "offer_accepted": True,
            "privacy_accepted": True,
        },
        headers={"X-Telegram-Init-Data": "dev"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["display_name"] == "Student Own Name"

    await db_session.refresh(learner)
    assert learner.bot_user_id is not None
    assert learner.display_name == "Teacher Named Learner"
    assert learner.notifications_enabled is True

    learners_count = (
        await db_session.execute(
            select(func.count()).select_from(Learner).where(Learner.tenant_id == tenant_1.id)
        )
    ).scalar_one()
    assert learners_count == 1


@pytest.mark.asyncio
async def test_register_student_invalid_token(client: AsyncClient, db_session: AsyncSession):
    """Test student registration with invalid invite token."""
    registration_data = {
        "invite_token": "invalid-token-12345",
        "student_name": "Jane Student",
        "offer_accepted": True,
        "privacy_accepted": True,
    }
    
    headers = {"X-Telegram-Init-Data": "dev"}
    
    response = await client.post("/api/v1/auth/register-student", json=registration_data, headers=headers)
    
    assert response.status_code == 404
    assert "Invalid invite code" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_student_used_token_returns_409(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
):
    teacher = await factories.create_user(db_session, role="teacher", tenant_id=tenant_1.id)
    await db_session.flush()
    invite_token = await factories.create_invite_token(
        db_session,
        tenant_id=tenant_1.id,
        created_by_user_id=teacher.id,
        used_at=datetime.now(timezone.utc),
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register-student",
        json={
            "invite_token": invite_token.token,
            "student_name": "Jane Student",
            "offer_accepted": True,
            "privacy_accepted": True,
        },
        headers={"X-Telegram-Init-Data": "dev"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "This invite code has already been used"


@pytest.mark.asyncio
async def test_register_student_expired_token_returns_410(
    client: AsyncClient,
    db_session: AsyncSession,
    tenant_1: Tenant,
):
    teacher = await factories.create_user(db_session, role="teacher", tenant_id=tenant_1.id)
    await db_session.flush()
    invite_token = await factories.create_invite_token(
        db_session,
        tenant_id=tenant_1.id,
        created_by_user_id=teacher.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    await db_session.commit()

    response = await client.post(
        "/api/v1/auth/register-student",
        json={
            "invite_token": invite_token.token,
            "student_name": "Jane Student",
            "offer_accepted": True,
            "privacy_accepted": True,
        },
        headers={"X-Telegram-Init-Data": "dev"},
    )

    assert response.status_code == 410
    assert response.json()["detail"] == "This invite code has expired"


@pytest.mark.asyncio
async def test_invite_token_consume_serializes_concurrent_sessions(async_engine):
    session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async with session_factory() as setup_session:
        tenant = Tenant(
            name="Invite Race Tenant",
            slug="invite-race",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        setup_session.add(tenant)
        await setup_session.flush()

        teacher = User(
            telegram_id=981001,
            username="invite_race_teacher",
            display_name="Invite Race Teacher",
            role="teacher",
            tenant_id=tenant.id,
            last_login_at=now,
        )
        setup_session.add(teacher)
        await setup_session.flush()

        invite_token = InviteToken(
            tenant_id=tenant.id,
            token="atomic-invite-token-12345",
            expires_at=now + timedelta(days=1),
            created_by_user_id=teacher.id,
            created_at=now,
        )
        setup_session.add(invite_token)
        await setup_session.commit()

    first_session = session_factory()
    second_session = session_factory()
    try:
        first_token = await crud.consume_invite_token_for_registration(
            first_session,
            "atomic-invite-token-12345",
        )
        assert first_token is not None

        second_task = asyncio.create_task(
            crud.consume_invite_token_for_registration(
                second_session,
                "atomic-invite-token-12345",
            )
        )
        await asyncio.sleep(0.2)
        assert not second_task.done()

        await first_session.commit()
        second_token = await asyncio.wait_for(second_task, timeout=2)

        assert second_token is None
    finally:
        await first_session.rollback()
        await second_session.rollback()
        await first_session.close()
        await second_session.close()


@pytest.mark.asyncio
async def test_unlink_student_registration_preserves_history_and_allows_reregistration(
    client: AsyncClient,
    db_session: AsyncSession,
    current_tenant: CurrentTenant,
    tenant_1: Tenant,
    monkeypatch,
):
    monkeypatch.setattr(config, "DEV_MODE", True)
    monkeypatch.setattr(config, "DEV_INIT_DATA", "dev")
    monkeypatch.setattr(config, "DEV_TELEGRAM_ID", 123456)
    monkeypatch.setattr(config, "DEV_USERNAME", "debug_student")
    monkeypatch.setattr(config, "DEV_DISPLAY_NAME", "Debug Student")

    learner = await factories.create_learner(
        db_session,
        tenant_id=tenant_1.id,
        display_name="Original Learner",
        chat_id=123456,
    )
    viewer = await factories.create_user(
        db_session,
        telegram_id=123456,
        username="debug_student",
        display_name="Debug Student",
        role="viewer",
        tenant_id=tenant_1.id,
    )
    await db_session.commit()
    bot_user_id = learner.bot_user_id
    headers, teacher_id = await get_auth_headers(db_session, current_tenant, role="teacher")

    unlink_response = await client.post(
        f"/api/v1/learners/{learner.id}/unlink-account",
        json={"reason": "debug reset"},
        headers=headers,
    )

    assert unlink_response.status_code == 200
    assert unlink_response.json()["chat_id"] is None
    assert unlink_response.json()["notifications_enabled"] is False

    await db_session.refresh(learner)
    await db_session.refresh(viewer)
    assert learner.bot_user_id is None
    assert learner.notifications_enabled is False
    assert viewer.tenant_id is None

    links = (
        await db_session.execute(
            select(LearnerAccountLink).where(LearnerAccountLink.learner_id == learner.id)
        )
    ).scalars().all()
    assert len(links) == 1
    assert links[0].telegram_id == 123456
    assert links[0].unlinked_at is not None
    assert links[0].unlinked_by_user_id == teacher_id
    assert links[0].unlink_reason == "debug reset"

    await db_session.commit()

    login_response = await client.post("/api/v1/auth/login", json={"init_data": "dev"})
    assert login_response.status_code == 404
    assert login_response.headers["X-Registration-Required"] == "true"

    invite_token = await factories.create_invite_token(
        db_session,
        tenant_id=tenant_1.id,
        created_by_user_id=teacher_id,
    )
    await db_session.commit()

    register_response = await client.post(
        "/api/v1/auth/register-student",
        json={
            "invite_token": invite_token.token,
            "student_name": "Debug Student Again",
            "offer_accepted": True,
            "privacy_accepted": True,
        },
        headers={"X-Telegram-Init-Data": "dev"},
    )

    assert register_response.status_code == 200
    body = register_response.json()
    assert body["user"]["id"] == viewer.id
    assert body["user"]["role"] == "viewer"

    users_count = (
        await db_session.execute(
            select(func.count()).select_from(User).where(User.telegram_id == 123456)
        )
    ).scalar_one()
    assert users_count == 1

    active_learner = await crud.get_learner_by_bot_user(
        db_session,
        current_tenant,
        bot_user_id,
    )
    assert active_learner is not None
    assert active_learner.id != learner.id
    assert active_learner.display_name == "Debug Student Again"

    active_links = (
        await db_session.execute(
            select(LearnerAccountLink).where(
                LearnerAccountLink.telegram_id == 123456,
                LearnerAccountLink.unlinked_at.is_(None),
            )
        )
    ).scalars().all()
    assert len(active_links) == 1
    assert active_links[0].learner_id == active_learner.id
