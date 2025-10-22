from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required, get_current_tenant, CurrentTenant
from api.schemas import (
    ReminderResponse,
    ReminderUpdateRequest,
    PaginationParams,
    PaginatedResponse,
)
from database import crud
from database.models import ReminderInstance

router = APIRouter()


def _reminder_type(instance: ReminderInstance) -> str | None:
    if instance.rule:
        return getattr(instance.rule, "reminder_type", None)
    return None


def _to_response(instance: ReminderInstance) -> ReminderResponse:
    return ReminderResponse(
        id=instance.id,
        package_id=instance.package_id,
        lesson_id=instance.lesson_id,
        reminder_type=_reminder_type(instance),
        scheduled_for=instance.scheduled_for,
        status=instance.status,
        active=instance.active,
        payload=instance.payload or {},
        comment=instance.comment,
        last_notified_at=instance.last_notified_at,
        last_response=instance.last_response,
        last_response_at=instance.last_response_at,
        last_decline_reason=instance.last_decline_reason,
    )


@router.get("", response_model=PaginatedResponse[ReminderResponse])
async def list_reminders(
    pagination: PaginationParams = Depends(),
    status_filter: str | None = Query(None, alias="status"),
    reminder_type: str | None = Query(None),
    package_id: int | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PaginatedResponse[ReminderResponse]:
    try:
        instances, total = await crud.fetch_reminder_instances_paginated(
            session,
            current_tenant,
            limit=pagination.limit,
            offset=pagination.offset,
            status=status_filter,
            reminder_type=reminder_type,
            package_id=package_id,
            search=search,
        )
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    
    items = [_to_response(instance) for instance in instances]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.get("/packages/{package_id}", response_model=PaginatedResponse[ReminderResponse])
async def list_reminders_for_package(
    package_id: int,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PaginatedResponse[ReminderResponse]:
    try:
        instances, total = await crud.fetch_reminder_instances_for_package_paginated(
            session,
            current_tenant,
            package_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    
    items = [_to_response(instance) for instance in instances]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: int,
    payload: ReminderUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> ReminderResponse:
    instance = await crud.get_reminder_instance(session, current_tenant, reminder_id)
    if not instance:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    try:
        await crud.set_reminder_instance_status(
            session,
            instance,
            status=payload.status or instance.status,
            active=payload.active if payload.active is not None else instance.active,
            comment=payload.comment if payload.comment is not None else instance.comment,
        )
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    refreshed = await crud.get_reminder_instance(session, current_tenant, reminder_id)
    if not refreshed:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return _to_response(refreshed)