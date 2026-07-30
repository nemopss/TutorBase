"""Payment API endpoints.

This module provides REST API endpoints for payment operations:
- POST /payments - Record a new payment
- GET /payments - List payments with filtering
- DELETE /payments/{id} - Delete a payment
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_current_user,
    get_session,
    require_maintenance_tenant_access,
)
from api.schemas.finance import PaymentCreate, PaymentResponse, PaymentUpdateRequest
from api.schemas import PaginatedResponse, PaginationParams
from database.models import Payment, Learner, Lesson, LessonPackage, User
from notifications.domain.enums import EventType
from services import finance_service
from services.notification_reconciliation import enqueue_notification_event_reconciliation

router = APIRouter()


@router.post("", response_model=PaymentResponse, status_code=201)
async def create_payment(
    request: PaymentCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_maintenance_tenant_access),
) -> PaymentResponse:
    """Record a new payment.
    
    Creates a payment record and updates the associated package's
    payment status if applicable.
    
    **Validates: Requirements 3.1**
    """
    # Verify learner exists and belongs to tenant
    learner = await session.get(Learner, request.learner_id)
    if not learner or learner.tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Learner not found")
    
    # Verify package if provided
    package = None
    package_title = None
    effective_package_id = request.package_id
    if request.package_id:
        package = await session.get(LessonPackage, request.package_id)
        if not package or package.tenant_id != current_tenant.tenant_id:
            raise HTTPException(status_code=404, detail="Package not found")
        if package.learner_id != request.learner_id:
            raise HTTPException(status_code=422, detail="Package does not belong to learner")
        package_title = package.title

    # Lessons are package-backed in the current model. If a lesson is specified,
    # bind the payment to that lesson's package so payment status stays in sync.
    if request.lesson_id:
        lesson = await session.get(Lesson, request.lesson_id)
        if not lesson or lesson.tenant_id != current_tenant.tenant_id:
            raise HTTPException(status_code=404, detail="Lesson not found")

        lesson_package = await session.get(LessonPackage, lesson.package_id)
        if not lesson_package or lesson_package.tenant_id != current_tenant.tenant_id:
            raise HTTPException(status_code=404, detail="Lesson not found")
        if lesson_package.learner_id != request.learner_id:
            raise HTTPException(status_code=422, detail="Lesson does not belong to learner")
        if request.package_id and lesson.package_id != request.package_id:
            raise HTTPException(status_code=422, detail="Lesson does not belong to package")

        if package is None:
            package = lesson_package
            effective_package_id = lesson.package_id
            package_title = lesson_package.title
    
    try:
        payment = await finance_service.record_payment(
            session,
            current_tenant,
            learner_id=request.learner_id,
            amount=request.amount,
            paid_at=request.paid_at,
            package_id=effective_package_id,
            lesson_id=request.lesson_id,
            notes=request.notes,
            actor_user_id=current_user.id,
        )
        if effective_package_id is not None:
            await enqueue_notification_event_reconciliation(
                session,
                current_tenant,
                event_type=EventType.PACKAGE,
                event_id=effective_package_id,
                reason="payment_recorded",
            )
        await session.commit()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    
    return PaymentResponse(
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
    )


@router.patch("/{payment_id}", response_model=PaymentResponse)
async def update_payment(
    payment_id: int,
    request: PaymentUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_maintenance_tenant_access),
) -> PaymentResponse:
    payment = await session.get(Payment, payment_id)
    if not payment or payment.tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Payment not found")
    if payment.voided_at is not None:
        raise HTTPException(status_code=409, detail="Voided payments cannot be edited")

    learner = await session.get(Learner, payment.learner_id)
    package_title = None
    if payment.package_id:
        package = await session.get(LessonPackage, payment.package_id)
        package_title = package.title if package else None

    try:
        payment = await finance_service.update_payment(
            session,
            payment,
            amount=request.amount,
            paid_at=request.paid_at,
            notes=request.notes,
            actor_user_id=current_user.id,
        )
        if payment.package_id is not None:
            await enqueue_notification_event_reconciliation(
                session,
                current_tenant,
                event_type=EventType.PACKAGE,
                event_id=payment.package_id,
                reason="payment_updated",
            )
        await session.commit()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return PaymentResponse(
        id=payment.id,
        learner_id=payment.learner_id,
        learner_name=learner.display_name if learner else None,
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
    )


@router.get("", response_model=PaginatedResponse[PaymentResponse])
async def list_payments(
    learner_id: Optional[int] = Query(None, description="Filter by learner"),
    from_date: Optional[datetime] = Query(None, description="Filter from date"),
    to_date: Optional[datetime] = Query(None, description="Filter to date"),
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PaginatedResponse[PaymentResponse]:
    """List payments with optional filtering.
    
    **Validates: Requirements 5.4**
    """
    # Build query
    query = (
        select(Payment)
        .where(
            Payment.tenant_id == current_tenant.tenant_id,
            Payment.voided_at.is_(None),
        )
        .order_by(Payment.paid_at.desc())
    )
    
    if learner_id:
        query = query.where(Payment.learner_id == learner_id)
    if from_date:
        query = query.where(Payment.paid_at >= from_date)
    if to_date:
        query = query.where(Payment.paid_at <= to_date)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.offset(pagination.offset).limit(pagination.limit)
    result = await session.execute(query)
    payments = result.scalars().all()
    
    # Build response items
    items = []
    for payment in payments:
        # Get learner name
        learner = await session.get(Learner, payment.learner_id)
        learner_name = learner.display_name if learner else None
        
        # Get package title
        package_title = None
        if payment.package_id:
            package = await session.get(LessonPackage, payment.package_id)
            package_title = package.title if package else None
        
        items.append(PaymentResponse(
            id=payment.id,
            learner_id=payment.learner_id,
            learner_name=learner_name,
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
    
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.delete("/{payment_id}", status_code=204)
async def delete_payment(
    payment_id: int,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_or_teacher_required),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    __=Depends(require_maintenance_tenant_access),
):
    """Void a payment and recalculate package status.
    
    **Validates: Requirements 3.2**
    """
    payment = await session.get(Payment, payment_id)
    if not payment or payment.tenant_id != current_tenant.tenant_id:
        raise HTTPException(status_code=404, detail="Payment not found")

    await finance_service.void_payment(
        session,
        payment,
        actor_user_id=current_user.id,
        reason="Voided via DELETE /payments/{payment_id}",
    )
    if payment.package_id is not None:
        await enqueue_notification_event_reconciliation(
            session,
            current_tenant,
            event_type=EventType.PACKAGE,
            event_id=payment.package_id,
            reason="payment_voided",
        )
    await session.commit()
