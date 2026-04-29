from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Tenant, TenantAccess, TenantAccessEvent
from services.exceptions import NotFoundError

ACCESS_STATUS_TRIAL = "trial"
ACCESS_STATUS_ACTIVE = "active"
ACCESS_STATUS_GRACE = "grace"
ACCESS_STATUS_EXPIRED = "expired"
ACCESS_STATUS_LIFETIME = "lifetime"
ACCESS_STATUS_SUSPENDED = "suspended"

ACCESS_MODE_FULL = "full"
ACCESS_MODE_GRACE = "grace"
ACCESS_MODE_BLOCKED = "blocked"

DEFAULT_TRIAL_DAYS = 14
DEFAULT_GRACE_DAYS = 7
DEFAULT_GRANT_DAYS = 30


@dataclass(frozen=True)
class TenantAccessSnapshot:
    tenant_id: int
    status: str
    mode: str
    access_until: datetime | None
    grace_until: datetime | None
    is_lifetime: bool
    reason: str | None = None

    @property
    def is_blocked(self) -> bool:
        return self.mode == ACCESS_MODE_BLOCKED


@dataclass(frozen=True)
class TenantAccessSyncResult:
    grace_started: int = 0
    expired: int = 0

    @property
    def changed(self) -> int:
        return self.grace_started + self.expired


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _serialize_state(access: TenantAccess | None) -> dict[str, Any] | None:
    if access is None:
        return None
    return {
        "status": access.status,
        "access_until": access.access_until.isoformat() if access.access_until else None,
        "grace_until": access.grace_until.isoformat() if access.grace_until else None,
        "notes": access.notes,
    }


def evaluate_access(access: TenantAccess | None, tenant_id: int, now: datetime | None = None) -> TenantAccessSnapshot:
    now = now or utc_now()

    if access is None:
        return TenantAccessSnapshot(
            tenant_id=tenant_id,
            status=ACCESS_STATUS_LIFETIME,
            mode=ACCESS_MODE_FULL,
            access_until=None,
            grace_until=None,
            is_lifetime=True,
            reason="legacy_missing_access_row",
        )

    access_until = _as_aware(access.access_until)
    grace_until = _as_aware(access.grace_until)

    if access.status == ACCESS_STATUS_SUSPENDED:
        return TenantAccessSnapshot(
            tenant_id=tenant_id,
            status=ACCESS_STATUS_SUSPENDED,
            mode=ACCESS_MODE_BLOCKED,
            access_until=access_until,
            grace_until=grace_until,
            is_lifetime=False,
            reason="tenant_suspended",
        )

    if access.status == ACCESS_STATUS_LIFETIME:
        return TenantAccessSnapshot(
            tenant_id=tenant_id,
            status=ACCESS_STATUS_LIFETIME,
            mode=ACCESS_MODE_FULL,
            access_until=None,
            grace_until=None,
            is_lifetime=True,
        )

    if access.status == ACCESS_STATUS_EXPIRED:
        return TenantAccessSnapshot(
            tenant_id=tenant_id,
            status=ACCESS_STATUS_EXPIRED,
            mode=ACCESS_MODE_BLOCKED,
            access_until=access_until,
            grace_until=grace_until,
            is_lifetime=False,
            reason="tenant_expired",
        )

    if access_until and now <= access_until:
        return TenantAccessSnapshot(
            tenant_id=tenant_id,
            status=access.status,
            mode=ACCESS_MODE_FULL,
            access_until=access_until,
            grace_until=grace_until,
            is_lifetime=False,
        )

    if grace_until and now <= grace_until:
        return TenantAccessSnapshot(
            tenant_id=tenant_id,
            status=ACCESS_STATUS_GRACE,
            mode=ACCESS_MODE_GRACE,
            access_until=access_until,
            grace_until=grace_until,
            is_lifetime=False,
            reason="tenant_in_grace_period",
        )

    return TenantAccessSnapshot(
        tenant_id=tenant_id,
        status=ACCESS_STATUS_EXPIRED,
        mode=ACCESS_MODE_BLOCKED,
        access_until=access_until,
        grace_until=grace_until,
        is_lifetime=False,
        reason="tenant_expired",
    )


async def get_access(session: AsyncSession, tenant_id: int) -> TenantAccess | None:
    result = await session.execute(select(TenantAccess).where(TenantAccess.tenant_id == tenant_id))
    return result.scalar_one_or_none()


async def get_access_snapshot(session: AsyncSession, tenant_id: int) -> TenantAccessSnapshot:
    access = await get_access(session, tenant_id)
    return evaluate_access(access, tenant_id)


async def ensure_access(
    session: AsyncSession,
    tenant_id: int,
    *,
    default_status: str = ACCESS_STATUS_LIFETIME,
    actor_user_id: int | None = None,
    notes: str | None = None,
) -> TenantAccess:
    access = await get_access(session, tenant_id)
    if access is not None:
        return access

    now = utc_now()
    access = TenantAccess(
        tenant_id=tenant_id,
        status=default_status,
        notes=notes,
        updated_by_user_id=actor_user_id,
        created_at=now,
        updated_at=now,
    )
    session.add(access)
    await session.flush()
    return access


async def create_trial_access(session: AsyncSession, tenant_id: int) -> TenantAccess:
    now = utc_now()
    access_until = now + timedelta(days=DEFAULT_TRIAL_DAYS)
    access = TenantAccess(
        tenant_id=tenant_id,
        status=ACCESS_STATUS_TRIAL,
        access_until=access_until,
        grace_until=access_until + timedelta(days=DEFAULT_GRACE_DAYS),
        notes="Created during tutor registration",
        created_at=now,
        updated_at=now,
    )
    session.add(access)
    await session.flush()
    return access


async def _get_tenant_or_404(session: AsyncSession, tenant_id: int) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError(f"Tenant {tenant_id} not found")
    return tenant


async def _record_event(
    session: AsyncSession,
    *,
    access: TenantAccess,
    actor_user_id: int | None,
    action: str,
    previous_state: dict[str, Any] | None,
    notes: str | None,
) -> None:
    event = TenantAccessEvent(
        tenant_id=access.tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        previous_state=previous_state,
        new_state=_serialize_state(access),
        notes=notes,
        created_at=utc_now(),
    )
    session.add(event)


async def sync_expired_access_states(
    session: AsyncSession,
    *,
    actor_user_id: int | None = None,
    now: datetime | None = None,
) -> TenantAccessSyncResult:
    """Persist time-based access transitions for Console, audit and jobs."""
    now = now or utc_now()
    now = _as_aware(now) or utc_now()

    result = await session.execute(
        select(TenantAccess).where(
            TenantAccess.status.in_(
                [
                    ACCESS_STATUS_TRIAL,
                    ACCESS_STATUS_ACTIVE,
                    ACCESS_STATUS_GRACE,
                ]
            )
        )
    )
    access_rows = list(result.scalars().all())

    grace_started = 0
    expired = 0
    for access in access_rows:
        access_until = _as_aware(access.access_until)
        grace_until = _as_aware(access.grace_until)
        previous_state = _serialize_state(access)

        if (
            (grace_until and now > grace_until)
            or (access_until and now > access_until and grace_until is None)
        ):
            if access.status != ACCESS_STATUS_EXPIRED:
                access.status = ACCESS_STATUS_EXPIRED
                access.updated_by_user_id = actor_user_id
                access.updated_at = now
                await _record_event(
                    session,
                    access=access,
                    actor_user_id=actor_user_id,
                    action="expired",
                    previous_state=previous_state,
                    notes="Access lifecycle sync",
                )
                expired += 1
            continue

        if (
            access.status in {ACCESS_STATUS_TRIAL, ACCESS_STATUS_ACTIVE}
            and access_until
            and now > access_until
            and grace_until
            and now <= grace_until
        ):
            access.status = ACCESS_STATUS_GRACE
            access.updated_by_user_id = actor_user_id
            access.updated_at = now
            await _record_event(
                session,
                access=access,
                actor_user_id=actor_user_id,
                action="grace_started",
                previous_state=previous_state,
                notes="Access lifecycle sync",
            )
            grace_started += 1

    if grace_started or expired:
        await session.flush()

    return TenantAccessSyncResult(grace_started=grace_started, expired=expired)


async def grant_access(
    session: AsyncSession,
    tenant_id: int,
    *,
    days: int = DEFAULT_GRANT_DAYS,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantAccess:
    await _get_tenant_or_404(session, tenant_id)
    access = await ensure_access(session, tenant_id, default_status=ACCESS_STATUS_ACTIVE)
    previous_state = _serialize_state(access)
    now = utc_now()
    base = access.access_until if access.access_until and _as_aware(access.access_until) > now else now
    access.status = ACCESS_STATUS_ACTIVE
    access.access_until = _as_aware(base) + timedelta(days=days)
    access.grace_until = access.access_until + timedelta(days=DEFAULT_GRACE_DAYS)
    access.updated_by_user_id = actor_user_id
    access.notes = notes
    access.updated_at = now
    await _record_event(
        session,
        access=access,
        actor_user_id=actor_user_id,
        action="grant",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return access


async def grant_lifetime_access(
    session: AsyncSession,
    tenant_id: int,
    *,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantAccess:
    await _get_tenant_or_404(session, tenant_id)
    access = await ensure_access(session, tenant_id, default_status=ACCESS_STATUS_LIFETIME)
    previous_state = _serialize_state(access)
    now = utc_now()
    access.status = ACCESS_STATUS_LIFETIME
    access.access_until = None
    access.grace_until = None
    access.updated_by_user_id = actor_user_id
    access.notes = notes
    access.updated_at = now
    await _record_event(
        session,
        access=access,
        actor_user_id=actor_user_id,
        action="grant_lifetime",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return access


async def set_access_until(
    session: AsyncSession,
    tenant_id: int,
    *,
    days_from_now: int,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantAccess:
    await _get_tenant_or_404(session, tenant_id)
    access = await ensure_access(session, tenant_id, default_status=ACCESS_STATUS_ACTIVE)
    previous_state = _serialize_state(access)
    now = utc_now()
    access_until = now + timedelta(days=days_from_now)
    access.status = ACCESS_STATUS_ACTIVE if days_from_now >= 0 else ACCESS_STATUS_EXPIRED
    access.access_until = access_until
    access.grace_until = (
        access_until + timedelta(days=DEFAULT_GRACE_DAYS)
        if days_from_now >= 0
        else access_until
    )
    access.updated_by_user_id = actor_user_id
    access.notes = notes
    access.updated_at = now
    await _record_event(
        session,
        access=access,
        actor_user_id=actor_user_id,
        action="set_until",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return access


async def suspend_access(
    session: AsyncSession,
    tenant_id: int,
    *,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantAccess:
    await _get_tenant_or_404(session, tenant_id)
    access = await ensure_access(session, tenant_id)
    previous_state = _serialize_state(access)
    now = utc_now()
    access.status = ACCESS_STATUS_SUSPENDED
    access.updated_by_user_id = actor_user_id
    access.notes = notes
    access.updated_at = now
    await _record_event(
        session,
        access=access,
        actor_user_id=actor_user_id,
        action="suspend",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return access


async def resume_access(
    session: AsyncSession,
    tenant_id: int,
    *,
    actor_user_id: int | None,
    notes: str | None = None,
) -> TenantAccess:
    await _get_tenant_or_404(session, tenant_id)
    access = await ensure_access(session, tenant_id)
    previous_state = _serialize_state(access)
    now = utc_now()
    access_until = _as_aware(access.access_until)
    grace_until = _as_aware(access.grace_until)

    if access_until is None and grace_until is None:
        access.status = ACCESS_STATUS_LIFETIME
    elif access_until and now <= access_until:
        access.status = ACCESS_STATUS_ACTIVE
    elif grace_until and now <= grace_until:
        access.status = ACCESS_STATUS_GRACE
    else:
        access.status = ACCESS_STATUS_EXPIRED

    access.updated_by_user_id = actor_user_id
    access.notes = notes
    access.updated_at = now
    await _record_event(
        session,
        access=access,
        actor_user_id=actor_user_id,
        action="resume",
        previous_state=previous_state,
        notes=notes,
    )
    await session.flush()
    return access
