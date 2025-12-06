from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    get_session,
    admin_or_teacher_required,
    get_current_tenant,
    CurrentTenant,
)
from api.schemas.learners import (
    LearnerListResponse,
    LearnerResponse,
    CreateLearnerFromChatIdRequest,
    UpdateLearnerNotificationsRequest,
    UpdateLearnerRequest,
)
from api.schemas import PaginatedResponse, PaginationParams
from services import learner_service

router = APIRouter()


@router.get("", response_model=PaginatedResponse[LearnerResponse])
async def list_all_learners(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> PaginatedResponse[LearnerResponse]:
    """Lists all learners for the current tenant."""
    learners = await learner_service.get_all_learners(session, current_tenant)
    
    # Apply pagination manually since service doesn't support it yet
    total = len(learners)
    paginated_learners = learners[pagination.offset:pagination.offset + pagination.limit]
    
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
    
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=learner.bot_user.chat_id if learner.bot_user else None,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
    )


@router.patch("/{learner_id}", response_model=LearnerResponse)
async def update_learner(
    learner_id: int,
    request: UpdateLearnerRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
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
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
        lesson_rate=float(learner.lesson_rate) if learner.lesson_rate else None,
    )


@router.patch("/{learner_id}/notifications", response_model=LearnerResponse)
async def update_learner_notifications(
    learner_id: int,
    request: UpdateLearnerNotificationsRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
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
    
    chat_id = learner.bot_user.chat_id if learner.bot_user else None
    return LearnerResponse(
        id=learner.id,
        display_name=learner.display_name,
        notifications_enabled=learner.notifications_enabled,
        chat_id=chat_id,
    )


@router.delete("/{learner_id}", status_code=204)
async def delete_learner(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
):
    """Delete a learner and all associated data (packages, lessons, reminders)."""
    deleted = await learner_service.delete_learner(
        session,
        current_tenant,
        learner_id=learner_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Learner not found")



@router.get("/{learner_id}/finance")
async def get_learner_finance(
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
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
        )
    )
    total_paid = total_result.scalar() or Decimal("0")
    
    # Get payment history
    payments_result = await session.execute(
        select(Payment)
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.learner_id == learner_id,
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
