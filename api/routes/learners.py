from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_session,
    require_full_tenant_access,
    require_maintenance_tenant_access,
)
from api.schemas.learners import (
    LearnerListResponse,
    LearnerResponse,
    LearnerDetailResponse,
    CreateLearnerFromChatIdRequest,
    UpdateLearnerNotificationsRequest,
    UpdateLearnerRequest,
    UnlinkLearnerAccountRequest,
)
from api.schemas.registration import InviteTokenResponse
from api.schemas.schedule import (
    LearnerScheduleResponse,
    UpdateScheduleRequest,
    AddSlotsRequest,
)
from api.schemas import PaginatedResponse, PaginationParams
from database.models import Lesson, LessonPackage
from services import learner_service
from services import schedule_service
from database import crud

router = APIRouter()


async def _get_next_lesson_dates(
    session: AsyncSession,
    learner_ids: list[int],
    tenant_id: int | None,
) -> dict[int, datetime | None]:
    """Get next lesson date for multiple learners in a single query.
    
    Args:
        session: Database session
        learner_ids: List of learner IDs to fetch
        tenant_id: Tenant ID for filtering
        
    Returns:
        Dict mapping learner_id to next_lesson_date (or None)
    """
    if not learner_ids:
        return {}
    
    now = datetime.now(timezone.utc)
    
    # Subquery to get minimum scheduled_at per learner
    query = (
        select(
            LessonPackage.learner_id,
            func.min(Lesson.scheduled_at).label('next_lesson_date')
        )
        .join(Lesson, Lesson.package_id == LessonPackage.id)
        .where(
            LessonPackage.learner_id.in_(learner_ids),
            Lesson.status.in_(['scheduled', 'rescheduled']),
            Lesson.scheduled_at > now,
        )
        .group_by(LessonPackage.learner_id)
    )
    
    if tenant_id is not None:
        query = query.where(LessonPackage.tenant_id == tenant_id)
    
    result = await session.execute(query)
    rows = result.all()
    
    # Build dict with all learner_ids defaulting to None
    next_dates: dict[int, datetime | None] = {lid: None for lid in learner_ids}
    for row in rows:
        next_dates[row.learner_id] = row.next_lesson_date
    
    return next_dates


@router.get("", response_model=PaginatedResponse[LearnerResponse])
async def list_all_learners(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PaginatedResponse[LearnerResponse]:
    """Lists all learners for the current tenant with next lesson dates."""
    learners = await learner_service.get_all_learners(session, current_tenant)
    
    # Apply pagination manually since service doesn't support it yet
    total = len(learners)
    paginated_learners = learners[pagination.offset:pagination.offset + pagination.limit]
    
    # Get next lesson dates for all paginated learners in one query
    learner_ids = [l.id for l in paginated_learners]
    next_lesson_dates = await _get_next_lesson_dates(
        session, learner_ids, current_tenant.tenant_id
    )
    
    items = []
    for learner in paginated_learners:
        chat_id = learner.bot_user.chat_id if learner.bot_user else None
        items.append(
            LearnerResponse(
                id=learner.id,
                display_name=learner.display_name,
                notifications_enabled=learner.notifications_enabled,
                chat_id=chat_id,
                lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
                next_lesson_date=next_lesson_dates.get(learner.id),
            )
        )
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.post("", response_model=LearnerResponse, status_code=201)
async def create_learner_from_chat_id(
    request: CreateLearnerFromChatIdRequest,
    session: AsyncSession = Depends(get_session),
    # We still need role check, but get tenant context separately
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> LearnerResponse:
    """Create a new learner from Telegram chat_id."""
    learner = await learner_service.create_learner_from_chat_id(
        session,
        current_tenant,
        chat_id=request.chat_id,
        display_name=request.display_name,
        notes=request.notes,
        notifications_enabled=request.notifications_enabled,
        lesson_rate=request.lesson_rate,
    )
    
    # New learner has no lessons yet
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=learner.bot_user.chat_id if learner.bot_user else None,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
        next_lesson_date=None,
    )


@router.patch("/{learner_id}", response_model=LearnerResponse)
async def update_learner(
    learner_id: int,
    request: UpdateLearnerRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> LearnerResponse:
    """Update a learner's details including lesson rate."""
    learner = await learner_service.update_learner(
        session,
        current_tenant,
        learner_id=learner_id,
        display_name=request.display_name,
        notes=request.notes,
        notifications_enabled=request.notifications_enabled,
        lesson_rate=request.lesson_rate,
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    # Get next lesson date for this learner
    next_lesson_dates = await _get_next_lesson_dates(
        session, [learner_id], current_tenant.tenant_id
    )
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
        next_lesson_date=next_lesson_dates.get(learner_id),
    )


@router.patch("/{learner_id}/notifications", response_model=LearnerResponse)
async def update_learner_notifications(
    learner_id: int,
    request: UpdateLearnerNotificationsRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_maintenance_tenant_access),
) -> LearnerResponse:
    """Enable or disable notifications for a learner."""
    learner = await learner_service.update_learner_notifications(
        session,
        current_tenant,
        learner_id=learner_id,
        notifications_enabled=request.notifications_enabled,
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    # Get next lesson date for this learner
    next_lesson_dates = await _get_next_lesson_dates(
        session, [learner_id], current_tenant.tenant_id
    )
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
        next_lesson_date=next_lesson_dates.get(learner_id),
    )


@router.post("/{learner_id}/unlink-account", response_model=LearnerResponse)
async def unlink_learner_account(
    learner_id: int,
    request: UnlinkLearnerAccountRequest,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> LearnerResponse:
    """Unlink a learner from Telegram without deleting learner history."""
    learner = await learner_service.get_learner_by_id(
        session,
        current_tenant,
        learner_id,
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")

    learner = await crud.unlink_learner_account(
        session,
        current_tenant,
        learner,
        unlinked_by_user_id=current_user.id,
        reason=request.reason,
    )
    await session.flush()

    next_lesson_dates = await _get_next_lesson_dates(
        session, [learner_id], current_tenant.tenant_id
    )

    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=None,
        bot_user_id=None,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
        next_lesson_date=next_lesson_dates.get(learner_id),
    )


@router.post("/{learner_id}/invite", response_model=InviteTokenResponse, status_code=201)
async def create_learner_invite(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_user=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> InviteTokenResponse:
    """Create a personal invite token for an unlinked learner."""
    learner = await learner_service.get_learner_by_id(
        session,
        current_tenant,
        learner_id,
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    if learner.bot_user_id is not None:
        raise HTTPException(
            status_code=409,
            detail="Learner is already linked to a Telegram account"
        )

    invite_token = await crud.create_invite_token(
        session=session,
        current_tenant=current_tenant,
        created_by_user_id=current_user.id,
        expires_in_days=30,
        learner_id=learner.id,
    )
    await session.flush()
    invite_token.learner = learner

    return InviteTokenResponse(
        id=invite_token.id,
        token=invite_token.token,
        expires_at=invite_token.expires_at,
        created_at=invite_token.created_at,
        is_used=invite_token.is_used,
        is_expired=invite_token.is_expired,
        is_valid=invite_token.is_valid,
        learner_id=learner.id,
        learner_name=learner.display_name,
    )


@router.delete("/{learner_id}", status_code=204)
async def delete_learner(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
):
    """Delete a learner and all associated data (packages, lessons, reminders)."""
    deleted = await learner_service.delete_learner(
        session,
        current_tenant,
        learner_id=learner_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Learner not found")


async def _get_first_package_date(
    session: AsyncSession,
    learner_id: int,
    tenant_id: int | None,
) -> datetime | None:
    """Get the date of the first package created for a learner.
    
    Args:
        session: Database session
        learner_id: Learner ID
        tenant_id: Tenant ID for filtering
        
    Returns:
        Date of first package creation or None if no packages
    """
    query = (
        select(func.min(LessonPackage.created_at))
        .where(LessonPackage.learner_id == learner_id)
    )
    
    if tenant_id is not None:
        query = query.where(LessonPackage.tenant_id == tenant_id)
    
    result = await session.execute(query)
    return result.scalar()


@router.get("/{learner_id}", response_model=LearnerDetailResponse)
async def get_learner_detail(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> LearnerDetailResponse:
    """Get detailed learner information for profile page.
    
    Returns learner details including next_lesson_date and first_package_date.
    """
    learner = await learner_service.get_learner_by_id(
        session, current_tenant, learner_id
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    # Get next lesson date
    next_lesson_dates = await _get_next_lesson_dates(
        session, [learner_id], current_tenant.tenant_id
    )
    
    # Get first package date
    first_package_date = await _get_first_package_date(
        session, learner_id, current_tenant.tenant_id
    )
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    
    return LearnerDetailResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
        notes=learner.notes,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
        next_lesson_date=next_lesson_dates.get(learner_id),
        first_package_date=first_package_date,
    )


@router.get("/{learner_id}/finance")
async def get_learner_finance(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
):
    """Get learner's financial profile.
    
    Returns lesson rate, outstanding balance, total paid, and payment history.
    
    **Validates: Requirements 5.4**
    """
    from decimal import Decimal
    from sqlalchemy import select, func
    from database.models import Learner, Payment, LessonPackage
    from api.schemas.finance import LearnerFinanceResponse, PaymentResponse
    from services import finance_service
    
    # Get learner
    learner = await session.get(Learner, learner_id)
    if not learner or learner.tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    # Get outstanding balance
    outstanding_balance = await finance_service.get_outstanding_balance(
        session, current_tenant, learner_id
    )
    
    # Get total paid
    total_result = await session.execute(
        select(func.coalesce(func.sum(Payment.amount), Decimal("0")))
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.learner_id == learner_id,
            Payment.voided_at.is_(None),
        )
    )
    total_paid = total_result.scalar() or Decimal("0")
    
    # Get payment history
    payments_result = await session.execute(
        select(Payment)
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.learner_id == learner_id,
            Payment.voided_at.is_(None),
        )
        .order_by(Payment.paid_at.desc())
    )
    payments = payments_result.scalars().all()
    
    payment_history = []
    for payment in payments:
        package_title = None
        if payment.package_id:
            package = await session.get(LessonPackage, payment.package_id)
            package_title = package.title if package else None
        
        payment_history.append(PaymentResponse(
            id=payment.id,
            learner_id=payment.learner_id,
            learner_name=learner.display_name,
            package_id=payment.package_id,
            package_title=package_title,
            lesson_id=payment.lesson_id,
            amount=payment.amount,
            currency=payment.currency,
            paid_at=payment.paid_at,
            notes=payment.notes,
            is_voided=payment.voided_at is not None,
            voided_at=payment.voided_at,
            void_reason=payment.void_reason,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
            tenant_id=payment.tenant_id,
        ))
    
    return LearnerFinanceResponse(
        learner_id=learner_id,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
        outstanding_balance=outstanding_balance,
        total_paid=total_paid,
        payment_history=payment_history,
    )


# --- Schedule Endpoints --- #

@router.get("/{learner_id}/schedule", response_model=LearnerScheduleResponse)
async def get_learner_schedule(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> LearnerScheduleResponse:
    """Get learner's weekly schedule.
    
    Returns the schedule with all slots and timezone.
    """
    # Verify learner exists and belongs to tenant
    learner = await learner_service.get_learner_by_id(
        session, current_tenant, learner_id
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    schedule = await schedule_service.get_learner_schedule(
        session, current_tenant, learner_id
    )
    
    return LearnerScheduleResponse(
        learner_id=learner_id,
        slots=schedule["slots"],
        timezone=schedule["timezone"],
    )


@router.put("/{learner_id}/schedule", response_model=LearnerScheduleResponse)
async def update_learner_schedule(
    learner_id: int,
    request: UpdateScheduleRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> LearnerScheduleResponse:
    """Replace learner's entire schedule.
    
    Replaces all existing slots with the provided slots.
    """
    # Verify learner exists and belongs to tenant
    learner = await learner_service.get_learner_by_id(
        session, current_tenant, learner_id
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    # Convert Pydantic models to dicts
    slots = [s.model_dump() for s in request.slots]
    
    schedule = await schedule_service.update_learner_schedule(
        session, current_tenant, learner_id, slots, request.timezone
    )
    
    return LearnerScheduleResponse(
        learner_id=learner_id,
        slots=schedule["slots"],
        timezone=schedule["timezone"],
    )


@router.post("/{learner_id}/schedule/slots", response_model=LearnerScheduleResponse)
async def add_schedule_slots(
    learner_id: int,
    request: AddSlotsRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> LearnerScheduleResponse:
    """Add slots for multiple days with the same time.
    
    Creates separate slots for each selected day.
    """
    # Verify learner exists and belongs to tenant
    learner = await learner_service.get_learner_by_id(
        session, current_tenant, learner_id
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    schedule = await schedule_service.add_schedule_slots(
        session, current_tenant, learner_id,
        days=request.days,
        time_str=request.time,
        duration=request.duration,
    )
    
    return LearnerScheduleResponse(
        learner_id=learner_id,
        slots=schedule["slots"],
        timezone=schedule["timezone"],
    )


@router.delete("/{learner_id}/schedule/slots/{slot_index}", response_model=LearnerScheduleResponse)
async def delete_schedule_slot(
    learner_id: int,
    slot_index: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_full_tenant_access),
) -> LearnerScheduleResponse:
    """Delete a single slot by index.
    
    The slot_index corresponds to the position in the slots array.
    """
    # Verify learner exists and belongs to tenant
    learner = await learner_service.get_learner_by_id(
        session, current_tenant, learner_id
    )
    if not learner:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    try:
        schedule = await schedule_service.delete_schedule_slot(
            session, current_tenant, learner_id, slot_index
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return LearnerScheduleResponse(
        learner_id=learner_id,
        slots=schedule["slots"],
        timezone=schedule["timezone"],
    )
