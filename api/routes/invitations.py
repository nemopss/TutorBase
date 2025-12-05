"""API routes for invite token management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_tenant, get_current_user, get_session, CurrentTenant
from api.schemas import (
    InviteTokenRequest,
    InviteTokenResponse,
    PaginationParams,
    PaginatedResponse,
)
from database import crud
from database.models import User

router = APIRouter(prefix="/tenants", tags=["invitations"])


@router.post("/{tenant_id}/invitations", response_model=InviteTokenResponse)
async def create_invite_token(
    tenant_id: int,
    request_data: InviteTokenRequest,
    current_user: User = Depends(get_current_user),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> InviteTokenResponse:
    """Generate a new invite token for the tenant.
    
    Only teachers and admins of the tenant can generate invite tokens.
    Students cannot generate invites.
    """
    
    # Verify user has permission to create invites for this tenant
    if current_tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only create invites for your own tenant"
        )
    
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can create invite tokens"
        )
    
    # Create the invite token
    invite_token = await crud.create_invite_token(
        session=session,
        current_tenant=current_tenant,
        created_by_user_id=current_user.id,
        expires_in_days=request_data.expires_in_days or 30,
    )
    
    await session.commit()
    await session.refresh(invite_token)
    
    return InviteTokenResponse(
        id=invite_token.id,
        token=invite_token.token,
        expires_at=invite_token.expires_at,
        created_at=invite_token.created_at,
        is_used=invite_token.is_used,
        is_expired=invite_token.is_expired,
        is_valid=invite_token.is_valid,
        note=request_data.note,
    )


@router.get("/{tenant_id}/invitations", response_model=PaginatedResponse[InviteTokenResponse])
async def list_invite_tokens(
    tenant_id: int,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
) -> PaginatedResponse[InviteTokenResponse]:
    """List invite tokens for the tenant.
    
    Only teachers and admins of the tenant can list invite tokens.
    Returns paginated list with usage statistics.
    """
    
    # Verify user has permission to list invites for this tenant
    if current_tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only list invites for your own tenant"
        )
    
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can list invite tokens"
        )
    
    # Get invite tokens
    tokens, total = await crud.list_invite_tokens(
        session=session,
        current_tenant=current_tenant,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    
    items = [
        InviteTokenResponse(
            id=token.id,
            token=token.token,
            expires_at=token.expires_at,
            created_at=token.created_at,
            is_used=token.is_used,
            is_expired=token.is_expired,
            is_valid=token.is_valid,
        )
        for token in tokens
    ]
    
    return PaginatedResponse.create(items, total, pagination.limit, pagination.offset)


@router.delete("/{tenant_id}/invitations/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite_token(
    tenant_id: int,
    token_id: int,
    current_user: User = Depends(get_current_user),
    current_tenant: CurrentTenant = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session),
):
    """Delete an invite token.
    
    Only teachers and admins of the tenant can delete invite tokens.
    Used tokens cannot be deleted.
    """
    
    # Verify user has permission to delete invites for this tenant
    if current_tenant.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete invites for your own tenant"
        )
    
    if current_user.role not in ["teacher", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers and admins can delete invite tokens"
        )
    
    # Get the token
    token = await crud.get_invite_token_by_id(session, current_tenant, token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invite token not found"
        )
    
    # Don't allow deleting used tokens
    if token.is_used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete a used invite token"
        )
    
    await crud.delete_invite_token(session, token)
    await session.commit()
