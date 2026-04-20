from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import admin_required, get_current_user, get_session
from api.schemas import (
    BroadcastAudienceUserResponse,
    BroadcastCampaignResponse,
    BroadcastCreateRequest,
    BroadcastPreviewRequest,
    BroadcastPreviewResponse,
    BroadcastRecipientResponse,
    BroadcastSendRequest,
    PaginatedResponse,
    PaginationParams,
    PlatformTenantResponse,
    TenantAccessActionRequest,
    TenantAccessGrantRequest,
    TenantAccessResponse,
    TenantAccessSyncResponse,
)
from database.models import BroadcastCampaign, BroadcastRecipient, Tenant, TenantAccess, User
from services import broadcast_service
from services import tenant_access_service
from services.exceptions import NotFoundError, ValidationError
from utils.tasks.broadcasts import send_broadcast_campaign_task

router = APIRouter()


def _access_response(
    access: TenantAccess | None,
    *,
    tenant_id: int,
) -> TenantAccessResponse:
    snapshot = tenant_access_service.evaluate_access(access, tenant_id)
    return TenantAccessResponse(
        tenant_id=tenant_id,
        status=snapshot.status,
        mode=snapshot.mode,
        access_until=snapshot.access_until,
        grace_until=snapshot.grace_until,
        is_lifetime=snapshot.is_lifetime,
        reason=snapshot.reason,
        notes=access.notes if access else None,
        bypass_access_restrictions=False,
    )


def _tenant_response(tenant: Tenant, access: TenantAccess | None) -> PlatformTenantResponse:
    return PlatformTenantResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        contact_email=tenant.contact_email,
        is_active=tenant.is_active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        access=_access_response(access, tenant_id=tenant.id),
    )


def _broadcast_campaign_response(campaign: BroadcastCampaign) -> BroadcastCampaignResponse:
    return BroadcastCampaignResponse(
        id=campaign.id,
        title=campaign.title,
        message_text=campaign.message_text,
        audience=campaign.audience,
        status=campaign.status,
        recipient_count=campaign.recipient_count,
        sent_count=campaign.sent_count,
        failed_count=campaign.failed_count,
        skipped_count=campaign.skipped_count,
        rate_limit_per_second=campaign.rate_limit_per_second,
        last_task_id=campaign.last_task_id,
        created_by_user_id=campaign.created_by_user_id,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
        queued_at=campaign.queued_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at,
    )


def _broadcast_recipient_response(recipient: BroadcastRecipient) -> BroadcastRecipientResponse:
    return BroadcastRecipientResponse(
        id=recipient.id,
        campaign_id=recipient.campaign_id,
        bot_user_id=recipient.bot_user_id,
        chat_id=recipient.chat_id,
        display_name=recipient.display_name,
        username=recipient.username,
        status=recipient.status,
        provider_message_id=recipient.provider_message_id,
        error_message=recipient.error_message,
        created_at=recipient.created_at,
        updated_at=recipient.updated_at,
        sent_at=recipient.sent_at,
    )


def _broadcast_audience_user_response(
    user: broadcast_service.BroadcastAudienceUser,
) -> BroadcastAudienceUserResponse:
    return BroadcastAudienceUserResponse(
        bot_user_id=user.bot_user_id,
        chat_id=user.chat_id,
        display_name=user.display_name,
        username=user.username,
        is_platform_admin=user.is_platform_admin,
    )


def _raise_service_error(exc: Exception) -> None:
    if isinstance(exc, NotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    raise exc


@router.get("/tenants", response_model=PaginatedResponse[PlatformTenantResponse])
async def list_platform_tenants(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> PaginatedResponse[PlatformTenantResponse]:
    total_result = await session.execute(select(func.count()).select_from(Tenant))
    total = total_result.scalar_one()

    tenants_result = await session.execute(
        select(Tenant)
        .order_by(Tenant.id)
        .limit(pagination.limit)
        .offset(pagination.offset)
    )
    tenants = list(tenants_result.scalars().all())
    tenant_ids = [tenant.id for tenant in tenants]

    access_by_tenant_id: dict[int, TenantAccess] = {}
    if tenant_ids:
        access_result = await session.execute(
            select(TenantAccess).where(TenantAccess.tenant_id.in_(tenant_ids))
        )
        access_by_tenant_id = {
            access.tenant_id: access for access in access_result.scalars().all()
        }

    items = [
        _tenant_response(tenant, access_by_tenant_id.get(tenant.id))
        for tenant in tenants
    ]
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.post("/broadcasts/preview", response_model=BroadcastPreviewResponse)
async def preview_platform_broadcast(
    payload: BroadcastPreviewRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> BroadcastPreviewResponse:
    try:
        preview = await broadcast_service.preview_broadcast_recipients(
            session,
            audience=payload.audience,
            bot_user_ids=payload.bot_user_ids,
            sample_limit=payload.sample_limit,
        )
    except (NotFoundError, ValidationError) as exc:
        _raise_service_error(exc)
    return BroadcastPreviewResponse(
        audience=preview.audience,
        total=preview.total,
        sample=[
            {
                "bot_user_id": item.bot_user_id,
                "chat_id": item.chat_id,
                "display_name": item.display_name,
                "username": item.username,
            }
            for item in preview.sample
        ],
    )


@router.get("/broadcasts/audience/users", response_model=PaginatedResponse[BroadcastAudienceUserResponse])
async def list_platform_broadcast_audience_users(
    search: str | None = Query(None, max_length=100),
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> PaginatedResponse[BroadcastAudienceUserResponse]:
    users, total = await broadcast_service.list_broadcast_audience_users(
        session,
        search=search,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.create(
        [_broadcast_audience_user_response(user) for user in users],
        total,
        pagination.limit,
        pagination.offset,
    )


@router.get("/broadcasts", response_model=PaginatedResponse[BroadcastCampaignResponse])
async def list_platform_broadcasts(
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> PaginatedResponse[BroadcastCampaignResponse]:
    campaigns, total = await broadcast_service.list_broadcast_campaigns(
        session,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return PaginatedResponse.create(
        [_broadcast_campaign_response(campaign) for campaign in campaigns],
        total,
        pagination.limit,
        pagination.offset,
    )


@router.post(
    "/broadcasts",
    response_model=BroadcastCampaignResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_platform_broadcast(
    payload: BroadcastCreateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> BroadcastCampaignResponse:
    try:
        campaign = await broadcast_service.create_broadcast_campaign(
            session,
            title=payload.title,
            message_text=payload.message_text,
            audience=payload.audience,
            bot_user_ids=payload.bot_user_ids,
            rate_limit_per_second=payload.rate_limit_per_second,
            created_by_user_id=current_user.id,
        )
        await session.commit()
    except (NotFoundError, ValidationError) as exc:
        await session.rollback()
        _raise_service_error(exc)
    return _broadcast_campaign_response(campaign)


@router.get("/broadcasts/{campaign_id}", response_model=BroadcastCampaignResponse)
async def get_platform_broadcast(
    campaign_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> BroadcastCampaignResponse:
    try:
        campaign = await broadcast_service.get_broadcast_campaign(session, campaign_id)
    except (NotFoundError, ValidationError) as exc:
        _raise_service_error(exc)
    return _broadcast_campaign_response(campaign)


@router.get(
    "/broadcasts/{campaign_id}/recipients",
    response_model=PaginatedResponse[BroadcastRecipientResponse],
)
async def list_platform_broadcast_recipients(
    campaign_id: int,
    pagination: PaginationParams = Depends(),
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> PaginatedResponse[BroadcastRecipientResponse]:
    try:
        recipients, total = await broadcast_service.list_broadcast_recipients(
            session,
            campaign_id=campaign_id,
            limit=pagination.limit,
            offset=pagination.offset,
        )
    except (NotFoundError, ValidationError) as exc:
        _raise_service_error(exc)
    return PaginatedResponse.create(
        [_broadcast_recipient_response(recipient) for recipient in recipients],
        total,
        pagination.limit,
        pagination.offset,
    )


@router.post("/broadcasts/{campaign_id}/send", response_model=BroadcastCampaignResponse)
async def send_platform_broadcast(
    campaign_id: int,
    payload: BroadcastSendRequest,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> BroadcastCampaignResponse:
    try:
        campaign = await broadcast_service.queue_broadcast_campaign(
            session,
            campaign_id=campaign_id,
            confirmation_text=payload.confirmation_text,
        )
        await session.commit()
        task = send_broadcast_campaign_task.delay(campaign_id=campaign.id)
        campaign.last_task_id = task.id
        await session.commit()
    except (NotFoundError, ValidationError) as exc:
        await session.rollback()
        _raise_service_error(exc)
    return _broadcast_campaign_response(campaign)


@router.get("/tenants/{tenant_id}", response_model=PlatformTenantResponse)
async def get_platform_tenant(
    tenant_id: int,
    session: AsyncSession = Depends(get_session),
    _=Depends(admin_required),
) -> PlatformTenantResponse:
    tenant = await session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    access_result = await session.execute(
        select(TenantAccess).where(TenantAccess.tenant_id == tenant_id)
    )
    return _tenant_response(tenant, access_result.scalar_one_or_none())


@router.post("/access/sync", response_model=TenantAccessSyncResponse)
async def sync_platform_tenant_access(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessSyncResponse:
    result = await tenant_access_service.sync_expired_access_states(
        session,
        actor_user_id=current_user.id,
    )
    await session.commit()
    return TenantAccessSyncResponse(
        grace_started=result.grace_started,
        expired=result.expired,
        changed=result.changed,
    )


@router.post("/tenants/{tenant_id}/access/grant", response_model=TenantAccessResponse)
async def grant_tenant_access(
    tenant_id: int,
    payload: TenantAccessGrantRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.grant_access(
            session,
            tenant_id,
            days=payload.days,
            actor_user_id=current_user.id,
            notes=payload.notes,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)


@router.post("/tenants/{tenant_id}/access/lifetime", response_model=TenantAccessResponse)
async def grant_tenant_lifetime_access(
    tenant_id: int,
    payload: TenantAccessActionRequest | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.grant_lifetime_access(
            session,
            tenant_id,
            actor_user_id=current_user.id,
            notes=payload.notes if payload else None,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)


@router.post("/tenants/{tenant_id}/access/suspend", response_model=TenantAccessResponse)
async def suspend_tenant_access(
    tenant_id: int,
    payload: TenantAccessActionRequest | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.suspend_access(
            session,
            tenant_id,
            actor_user_id=current_user.id,
            notes=payload.notes if payload else None,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)


@router.post("/tenants/{tenant_id}/access/resume", response_model=TenantAccessResponse)
async def resume_tenant_access(
    tenant_id: int,
    payload: TenantAccessGrantRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(admin_required),
) -> TenantAccessResponse:
    try:
        access = await tenant_access_service.resume_access(
            session,
            tenant_id,
            actor_user_id=current_user.id,
            days=payload.days,
            notes=payload.notes,
        )
        await session.commit()
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return _access_response(access, tenant_id=tenant_id)
