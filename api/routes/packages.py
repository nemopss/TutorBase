from __future__ import annotations

from datetime import datetime, time, date

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required, admin_required, get_current_tenant, CurrentTenant, get_current_user
from api.schemas.packages import (
    PackageCreateRequest,
    PackageListResponse,
    PackageResponse,
    PackageUpdateRequest,
    PackageProgressModel,
)
from api.schemas import MessageResponse, PaginatedResponse, PaginationParams
from services import package_service, template_service
from services.dto import LessonPackageDTO
from services.exceptions import NotFoundError, ValidationError
from utils.timezone import DEFAULT_TIMEZONE, DEFAULT_TZ, parse_date_string, normalize_to_timezone
from utils.tasks.reminders import regenerate_package_reminders_task
from utils.tasks import bulk_sync_package_metrics_task
from database import crud
from database.models import User

router = APIRouter()


def _to_response(dto: LessonPackageDTO) -> PackageResponse:
    progress = PackageProgressModel(
        total=dto.progress.total,
        completed=dto.progress.completed,
        cancelled=dto.progress.cancelled,
    )

    return PackageResponse(
        id=dto.id,
        learner_id=dto.learner_id,
        learner_name=dto.learner_name,
        template_id=dto.template_id,
        title=dto.title,
        status=dto.status,
        start_date=dto.start_date,
        end_date=dto.end_date,
        timezone=DEFAULT_TIMEZONE,
        notes=dto.notes,
        total_lessons=dto.total_lessons,
        progress=progress,
    )


def _parse_start_date(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return parse_date_string(value, DEFAULT_TZ)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD.",
            ) from exc
    return value


@router.get("", response_model=PaginatedResponse[PackageResponse])
async def list_packages(
    pagination: PaginationParams = Depends(),
    learner_id: int | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[PackageResponse]:
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

    packages, total = await package_service.list_packages(
        session,
        current_tenant,
        limit=pagination.limit,
        offset=pagination.offset,
        learner_id=learner_id,
        status=status_filter,
        search=search,
    )
    items = [_to_response(pkg) for pkg in packages]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.get("/{package_id}", response_model=PackageResponse)
async def get_package_endpoint(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
) -> PackageResponse:
    try:
        package = await package_service.get_package(session, current_tenant, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(package)


@router.post("/create", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package_endpoint(
    payload: PackageCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PackageResponse:
    try:
        start_local = _parse_start_date(payload.start_date)
        if payload.template_id is not None:
            await template_service.get_template(session, current_tenant, payload.template_id)
            package = await package_service.create_package_from_template(
                session,
                current_tenant,
                learner_id=payload.learner_id,
                template_id=payload.template_id,
                title=payload.title,
                notes=payload.notes,
                start_local=start_local,
                status=payload.status or 'draft',
            )
        else:
            package = await package_service.create_package(
                session,
                current_tenant,
                learner_id=payload.learner_id,
                title=payload.title,
                notes=payload.notes,
                status=payload.status,
                start_date=start_local,
                total_lessons=payload.total_lessons,
            )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(package)


@router.patch("/{package_id}", response_model=PackageResponse)
async def update_package_endpoint(
    package_id: int,
    payload: PackageUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> PackageResponse:
    try:
        package = await package_service.update_package(
            session,
            current_tenant,
            package_id,
            title=payload.title,
            status=payload.status,
            notes=payload.notes,
            start_date=normalize_to_timezone(payload.start_date) if payload.start_date is not None else None,
            end_date=normalize_to_timezone(payload.end_date) if payload.end_date is not None else None,
            total_lessons=payload.total_lessons,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(package)


@router.delete("/{package_id}")
async def delete_package_endpoint(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> Response:
    try:
        await package_service.delete_package(session, current_tenant, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{package_id}/regenerate", response_model=MessageResponse)
async def regenerate_package_endpoint(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> MessageResponse:
    """Regenerate reminders for a package in background.
    
    This endpoint enqueues a background task to regenerate all reminder rules
    and instances for the specified package. The operation is non-blocking and
    returns immediately.
    """
    try:
        # Verify package exists before enqueuing task
        package = await package_service.get_package(session, current_tenant, package_id)
        
        # Enqueue background task (non-blocking)
        task = regenerate_package_reminders_task.delay(package_id, current_tenant.tenant_id)
        
        return MessageResponse(
            detail=f"Reminder regeneration started for package '{package.title}' (task_id: {task.id})"
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/bulk-sync-metrics", response_model=MessageResponse)
async def bulk_sync_metrics_endpoint(
    package_ids: list[int] = Query(..., description="List of package IDs to sync metrics for"),
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_required),
) -> MessageResponse:
    """Synchronize metrics for multiple packages in background.
    
    This endpoint enqueues a background task to sync metrics for multiple packages.
    Useful for bulk operations after data imports or migrations. The operation is
    non-blocking and returns immediately.
    
    Args:
        package_ids: List of package IDs to sync metrics for
        
    Returns:
        MessageResponse with task ID and status
        
    Example:
        POST /api/v1/packages/bulk-sync-metrics?package_ids=1&package_ids=2&package_ids=3
    """
    if not package_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one package_id is required"
        )
    
    if len(package_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 packages can be synced at once"
        )
    
    # Enqueue background task (non-blocking)
    task = bulk_sync_package_metrics_task.delay(
        package_ids=package_ids,
        tenant_id=current_tenant.tenant_id,
        chunk_size=10
    )
    
    return MessageResponse(
        detail=f"Bulk metrics sync started for {len(package_ids)} packages (task_id: {task.id})"
    )
