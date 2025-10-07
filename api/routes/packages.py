from __future__ import annotations

from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session, admin_or_teacher_required, admin_required
from api.schemas.packages import (
    PackageCreateRequest,
    PackageListResponse,
    PackageResponse,
    PackageUpdateRequest,
    PackageProgressModel,
)
from api.schemas import MessageResponse
from services import package_service
from services.dto import LessonPackageDTO
from services.exceptions import NotFoundError, ValidationError

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
        timezone=dto.timezone,
        notes=dto.notes,
        total_lessons=dto.total_lessons,
        progress=progress,
    )


@router.get("", response_model=PackageListResponse)
async def list_packages(  # pragma: no cover - thin wrapper
    limit: int = Query(10, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    learner_id: int | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> PackageListResponse:
    packages, total = await package_service.list_packages(
        session,
        limit=limit,
        offset=offset,
        learner_id=learner_id,
        status=status_filter,
        search=search,
    )
    return PackageListResponse(
        total=total,
        items=[_to_response(pkg) for pkg in packages],
    )


@router.get("/{package_id}", response_model=PackageResponse)
async def get_package_endpoint(
    package_id: int,
    session: AsyncSession = Depends(get_session),
) -> PackageResponse:
    try:
        package = await package_service.get_package(session, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _to_response(package)


@router.post("/create", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
async def create_package_endpoint(
    payload: PackageCreateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> PackageResponse:
    try:
        if payload.template_id is not None:
            if payload.start_date is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start_date required for template")
            tz_name = payload.timezone or 'Europe/Moscow'
            start_local = payload.start_date
            if start_local.tzinfo is None:
                start_local = start_local.replace(tzinfo=ZoneInfo(tz_name))
            package = await package_service.create_package_from_template(
                session,
                learner_id=payload.learner_id,
                template_id=payload.template_id,
                title=payload.title,
                notes=payload.notes,
                start_local=start_local,
                timezone_name=tz_name,
            )
        else:
            package = await package_service.create_package(
                session,
                learner_id=payload.learner_id,
                title=payload.title,
                notes=payload.notes,
                status=payload.status,
                timezone_name=payload.timezone,
                start_date=payload.start_date,
                total_lessons=payload.total_lessons,
            )
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(package)


@router.patch("/{package_id}", response_model=PackageResponse)
async def update_package_endpoint(
    package_id: int,
    payload: PackageUpdateRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> PackageResponse:
    try:
        package = await package_service.update_package(
            session,
            package_id,
            title=payload.title,
            status=payload.status,
            notes=payload.notes,
            timezone_name=payload.timezone,
            start_date=payload.start_date,
            end_date=payload.end_date,
            total_lessons=payload.total_lessons,
        )
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _to_response(package)


@router.delete("/{package_id}")
async def delete_package_endpoint(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_required),
) -> Response:
    try:
        await package_service.delete_package(session, package_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{package_id}/regenerate", response_model=MessageResponse)
async def regenerate_package_endpoint(
    package_id: int,
    session: AsyncSession = Depends(get_session),
    user=Depends(admin_or_teacher_required),
) -> MessageResponse:
    try:
        await package_service.regenerate_reminders_for_package(session, package_id)
        await session.commit()
    except NotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    package = await package_service.get_package(session, package_id)
    return MessageResponse(detail=f"Reminders regenerated for package '{package.title}'")
