from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required
from api.schemas import (
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdateRequest,
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


@router.get("", response_model=ReminderListResponse)
async def list_reminders(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: str | None = Query(None, alias="status"),
    reminder_type: str | None = Query(None),
    package_id: int | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> ReminderListResponse:
    try:
        instances, total = await crud.fetch_reminder_instances_paginated(
            session,
            limit=limit,
            offset=offset,
            status=status_filter,
            reminder_type=reminder_type,
            package_id=package_id,
            search=search,
        )
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ReminderListResponse(total=total, items=[_to_response(instance) for instance in instances])


@router.get("/packages/{package_id}", response_model=ReminderListResponse)
async def list_reminders_for_package(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> ReminderListResponse:
    try:
        instances = await crud.fetch_reminder_instances_for_package(session, package_id)
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return ReminderListResponse(total=len(instances), items=[_to_response(instance) for instance in instances])


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(
    reminder_id: int,
    payload: ReminderUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> ReminderResponse:
    instance = await crud.get_reminder_instance(session, reminder_id)
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

    refreshed = await crud.get_reminder_instance(session, reminder_id)
    if not refreshed:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return _to_response(refreshed)
