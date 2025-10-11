from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, get_current_user
from api.dependencies import admin_or_teacher_required
from api.schemas import (
    LessonCreateRequest,
    LessonListResponse,
    LessonResponse,
    LessonUpdateRequest,
)
from services import lesson_service, package_service
from services.dto import LessonDTO
from services.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=LessonListResponse)
async def list_all_lessons_endpoint(
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    sort_by: str = 'scheduled_at',
    sort_order: str = 'asc',
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LessonListResponse:
    lessons, total = await lesson_service.list_all_lessons(
        session, 
        status=status, 
        search=search,
        limit=limit, 
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return LessonListResponse(total=total, items=[_to_response(lesson) for lesson in lessons])


def _to_response(dto: LessonDTO) -> LessonResponse:
    return LessonResponse(
        id=dto.id,
        package_id=dto.package_id,
        package_title=dto.package_title,
        learner_name=dto.learner_name,
        scheduled_at=dto.scheduled_at,
        status=dto.status,
        duration_minutes=dto.duration_minutes,
        sequence_index=dto.sequence_index,
        teacher_notes=dto.teacher_notes,
        homework_due_at=dto.homework_due_at,
        timezone="Europe/Moscow",
    )


@router.get("/packages/{package_id}", response_model=LessonListResponse)
async def list_lessons_for_package(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LessonListResponse:
    try:
        lessons = await lesson_service.list_lessons(session, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return LessonListResponse(total=len(lessons), items=[_to_response(lesson) for lesson in lessons])


@router.post("/packages/{package_id}", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson_for_package(
    package_id: int,
    payload: LessonCreateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> LessonResponse:
    try:
        existing = await lesson_service.list_lessons(session, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    sequence_index = max((lesson.sequence_index or 0 for lesson in existing), default=0) + 1

    try:
        lesson = await lesson_service.create_lesson(
            session,
            package_id=package_id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            status=payload.status,
            teacher_notes=payload.teacher_notes,
            homework_due_at=payload.homework_due_at,
            sequence_index=sequence_index,
        )
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(lesson)


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson_endpoint(
    lesson_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(get_current_user),
) -> LessonResponse:
    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(lesson)


@router.patch("/{lesson_id}", response_model=LessonResponse)
async def update_lesson_endpoint(
    lesson_id: int,
    payload: LessonUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> LessonResponse:
    try:
        lesson = await lesson_service.update_lesson(
            session,
            lesson_id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            status=payload.status,
            teacher_notes=payload.teacher_notes,
            homework_due_at=payload.homework_due_at,
        )
        await package_service.regenerate_reminders_for_package(session, lesson.package_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(lesson)


@router.delete("/{lesson_id}")
async def delete_lesson_endpoint(
    lesson_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
):
    try:
        lesson = await lesson_service.get_lesson(session, lesson_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        await lesson_service.delete_lesson(session, lesson_id)
        await package_service.regenerate_reminders_for_package(session, lesson.package_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
