from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    CurrentTenant,
    admin_or_teacher_required,
    get_current_tenant,
    get_session,
    require_full_tenant_access,
)
from api.schemas.groups import (
    LearnerGroupCreateRequest,
    LearnerGroupMemberResponse,
    LearnerGroupMembersRequest,
    LearnerGroupResponse,
    LearnerGroupUpdateRequest,
)
from notifications.application.dto import (
    LearnerGroupDraft,
    LearnerGroupMemberRecord,
    LearnerGroupRecord,
    LearnerGroupUpdateDraft,
)
from notifications.application.groups import (
    AddLearnerGroupMembersUseCase,
    CreateLearnerGroupUseCase,
    DeactivateLearnerGroupMemberUseCase,
    GetLearnerGroupUseCase,
    ListLearnerGroupsUseCase,
    UpdateLearnerGroupUseCase,
)
from notifications.infrastructure.repositories import SqlAlchemySessionNotificationUnitOfWork

router = APIRouter()


@router.get("", response_model=list[LearnerGroupResponse])
async def list_learner_groups(
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> list[LearnerGroupResponse]:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=_require_tenant_id(current_tenant))
    groups = await ListLearnerGroupsUseCase(uow).execute()
    return [_group_response(group) for group in groups]


@router.post("", response_model=LearnerGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_learner_group(
    payload: LearnerGroupCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_full_tenant_access),
) -> LearnerGroupResponse:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=_require_tenant_id(current_tenant))
    try:
        group = await CreateLearnerGroupUseCase(uow).execute(
            LearnerGroupDraft(
                name=payload.name,
                description=payload.description,
                color=payload.color,
                learner_ids=tuple(payload.learner_ids),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _group_response(group)


@router.get("/{group_id}", response_model=LearnerGroupResponse)
async def get_learner_group(
    group_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
) -> LearnerGroupResponse:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=_require_tenant_id(current_tenant))
    group = await GetLearnerGroupUseCase(uow).execute(group_id)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_response(group)


@router.patch("/{group_id}", response_model=LearnerGroupResponse)
async def update_learner_group(
    group_id: int,
    payload: LearnerGroupUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_full_tenant_access),
) -> LearnerGroupResponse:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=_require_tenant_id(current_tenant))
    group = await UpdateLearnerGroupUseCase(uow).execute(
        group_id=group_id,
        draft=LearnerGroupUpdateDraft(
            name=payload.name,
            description=payload.description,
            color=payload.color,
            status=payload.status,
        ),
    )
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_response(group)


@router.post("/{group_id}/members", response_model=LearnerGroupResponse)
async def add_learner_group_members(
    group_id: int,
    payload: LearnerGroupMembersRequest,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_full_tenant_access),
) -> LearnerGroupResponse:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=_require_tenant_id(current_tenant))
    try:
        group = await AddLearnerGroupMembersUseCase(uow).execute(
            group_id=group_id,
            learner_ids=tuple(payload.learner_ids),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_response(group)


@router.delete("/{group_id}/members/{learner_id}", response_model=LearnerGroupResponse)
async def deactivate_learner_group_member(
    group_id: int,
    learner_id: int,
    session: AsyncSession = Depends(get_session),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    _=Depends(admin_or_teacher_required),
    __=Depends(require_full_tenant_access),
) -> LearnerGroupResponse:
    uow = SqlAlchemySessionNotificationUnitOfWork(session, tenant_id=_require_tenant_id(current_tenant))
    group = await DeactivateLearnerGroupMemberUseCase(uow).execute(
        group_id=group_id,
        learner_id=learner_id,
    )
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    return _group_response(group)


def _require_tenant_id(current_tenant: CurrentTenant) -> int:
    if current_tenant.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Group APIs require a tenant context",
        )
    return current_tenant.tenant_id


def _group_response(group: LearnerGroupRecord) -> LearnerGroupResponse:
    return LearnerGroupResponse(
        id=group.group_id,
        name=group.name,
        description=group.description,
        color=group.color,
        status=group.status,
        member_count=group.member_count,
        members=[_member_response(member) for member in group.members],
        created_at=group.created_at,
        updated_at=group.updated_at,
    )


def _member_response(member: LearnerGroupMemberRecord) -> LearnerGroupMemberResponse:
    return LearnerGroupMemberResponse(
        learner_id=member.learner_id,
        display_name=member.display_name,
        status=member.status,
        joined_at=member.joined_at,
        left_at=member.left_at,
    )
