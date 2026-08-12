from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_current_user,
    get_session,
    require_full_tenant_access,
    require_maintenance_tenant_access,
)
from api.schemas import (
    LessonCreateRequest,
    LessonListResponse,
    LessonResponse,
    LessonUpdateRequest,
    MessageResponse,
    PaginatedResponse,
    PaginationParams,
)
from services import lesson_service, package_service
from services.dto import LessonDTO
from database import crud
from database.models import User
from services.exceptions import NotFoundError, ValidationError

router = APIRouter()


@router.get("", response_model=PaginatedResponse[LessonResponse])
async def list_all_lessons_endpoint(
    pagination: PaginationParams = Depends(),
    status: Optional[str] = None,
    learner_id: Optional[int] = None,
    search: Optional[str] = None,
    from_date: datetime | None = Query(None),
    to_date: datetime | None = Query(None),
    sort_by: str = 'scheduled_at',
    sort_order: str = 'asc',
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[LessonResponse]:
    # Enforce learner_id for viewers (students)
    if current_user.role == 'viewer':
        if not current_user.telegram_id:
            return PaginatedResponse.create([], 0, pagination.limit, pagination.offset)
            
        bot_user = await crud.get_bot_user_by_chat_id(session, current_user.telegram_id)
        if not bot_user:
            return PaginatedResponse.create([], 0, pagination.limit, pagination.offset)
            
        learner = await crud.get_learner_by_bot_user(session, current_tenant, bot_user.id)
        if not learner:
            return PaginatedResponse.create([], 0, pagination.limit, pagination.offset)
            
        learner_id = learner.id

    lessons, total = await lesson_service.list_all_lessons(
        session, 
        current_tenant,
        status=status, 
        learner_id=learner_id,
        search=search,
        from_date=from_date,
        to_date=to_date,
        limit=pagination.limit, 
        offset=pagination.offset,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    include_private = current_user.role != "viewer"
    items = [_to_response(lesson, include_private=include_private) for lesson in lessons]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


def _to_response(dto: LessonDTO, *, include_private: bool = True) -> LessonResponse:
    return LessonResponse(
        id=dto.id,
        package_id=dto.package_id,
        package_title=dto.package_title if include_private else None,
        learner_name=dto.learner_name,
        scheduled_at=dto.scheduled_at,
        status=dto.status,
        duration_minutes=dto.duration_minutes,
        sequence_index=dto.sequence_index,
        teacher_notes=dto.teacher_notes if include_private else None,
        homework_due_at=dto.homework_due_at,
        timezone="Europe/Moscow",
    )


@router.get("/packages/{package_id}", response_model=PaginatedResponse[LessonResponse])
async def list_lessons_for_package(
    package_id: int,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PaginatedResponse[LessonResponse]:
    try:
        lessons = await lesson_service.list_lessons(session, current_tenant, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    
    # Apply pagination manually since service doesn't support it yet
    total = len(lessons)
    paginated_lessons = lessons[pagination.offset:pagination.offset + pagination.limit]
    items = [_to_response(lesson) for lesson in paginated_lessons]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.post("/packages/{package_id}", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson_for_package(
    package_id: int,
    payload: LessonCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_full_tenant_access),
) -> LessonResponse:
    try:
        existing = await lesson_service.list_lessons(session, current_tenant, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    sequence_index = max((lesson.sequence_index or 0 for lesson in existing), default=0) + 1

    try:
        lesson = await lesson_service.create_lesson(
            session,
            current_tenant,
            package_id=package_id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            status=payload.status,
            teacher_notes=payload.teacher_notes,
            homework_due_at=payload.homework_due_at,
            sequence_index=sequence_index,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(lesson)


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson_endpoint(
    lesson_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> LessonResponse:
    try:
        lesson = await lesson_service.get_lesson(session, current_tenant, lesson_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(lesson)


@router.patch("/{lesson_id}", response_model=LessonResponse)
async def update_lesson_endpoint(
    lesson_id: int,
    payload: LessonUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_maintenance_tenant_access),
) -> LessonResponse:
    try:
        lesson = await lesson_service.update_lesson(
            session,
            current_tenant,
            lesson_id=lesson_id,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            status=payload.status,
            teacher_notes=payload.teacher_notes,
            homework_due_at=payload.homework_due_at,
            teacher_notes_set="teacher_notes" in payload.model_fields_set,
            homework_due_at_set="homework_due_at" in payload.model_fields_set,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(lesson)


@router.delete("/{lesson_id}")
async def delete_lesson_endpoint(
    lesson_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_full_tenant_access),
):
    try:
        await lesson_service.delete_lesson(session, current_tenant, lesson_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)
