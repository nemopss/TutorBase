from datetime import datetime, timezone
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import get_session, get_current_tenant, CurrentTenant, get_current_user
from database.models import Tenant, User
from api.schemas import (
    RefreshRequest,
    SwitchTenantRequest,
    TokenPairResponse,
    UserPayload,
    WebAppLoginRequest,
)
from api.security import (
    InitDataVerificationError,
    TokenType,
    TokenVerificationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_telegram_init_data,
)
from config import config
from database import crud

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Helper function to apply rate limiting conditionally
def rate_limit(limit_string: str):
    """Apply rate limiting only in production mode."""
    if config.DEV_MODE:
        # In dev mode, return a no-op decorator
        def decorator(func):
            return func
        return decorator
    else:
        # In production, apply actual rate limiting
        return limiter.limit(limit_string)


def _build_display_name(user_payload: Dict[str, object]) -> str:
    first_name = user_payload.get("first_name") or ""
    last_name = user_payload.get("last_name") or ""
    username = user_payload.get("username")
    display = " ".join(part for part in (first_name, last_name) if part)
    if display:
        return display
    if username:
        return str(username)
    telegram_id = user_payload.get("id")
    return f"tg:{telegram_id}" if telegram_id is not None else "Telegram User"


async def _persist_user(session: AsyncSession, current_tenant: CurrentTenant, user_data: Dict[str, object]):
    telegram_id = int(user_data["id"])
    username = user_data.get("username")
    display_name = _build_display_name(user_data)

    user = await crud.get_user_by_telegram_id(session, telegram_id)
    now = datetime.now(timezone.utc)
    is_admin = telegram_id in config.ADMINS
    default_role = "admin" if is_admin else "viewer"

    if user is None:
        # НОВЫЙ ПОЛЬЗОВАТЕЛЬ - требуется регистрация!
        # Возвращаем None, чтобы login endpoint мог обработать это
        return None
    else:
        role_update = "admin" if is_admin and user.role != "admin" else None
        user = await crud.update_user_login_metadata(
            session,
            user,
            username=username,
            display_name=display_name,
            role=role_update,
            last_login_at=now,
        )
    await session.flush()
    return user


@router.post("/login", response_model=TokenPairResponse)
@rate_limit("5/minute")  # Protect against brute force (disabled in dev mode)
async def login(
    request: Request,
    payload: WebAppLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:    # This endpoint is special: it creates the user, so tenant context doesn't exist yet.
    # We create a placeholder context. A super_admin will be created without a tenant,
    # and a regular user will be assigned to the default tenant (id=1).
    # This logic is handled inside crud.create_user.
    # For the purpose of satisfying the dependency, we can create a temporary one.
    # NOTE: This is a simplification for the login flow.
    current_tenant = CurrentTenant(tenant_id=None, is_super_admin=True)
    init_payload: Dict[str, object]
    if config.DEV_MODE and payload.init_data == config.DEV_INIT_DATA:
        logging.getLogger(__name__).info("DEV_MODE active – using mock Telegram payload")
        init_payload = {
            "user": {
                "id": config.DEV_TELEGRAM_ID,
                "first_name": config.DEV_DISPLAY_NAME,
                "username": config.DEV_USERNAME,
            }
        }
    else:
        try:
            init_payload = verify_telegram_init_data(payload.init_data, config.BOT_TOKEN)
        except InitDataVerificationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user_block = init_payload.get("user")
    if not isinstance(user_block, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user payload")

    telegram_id = user_block.get("id")
    if telegram_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing user id")

    user = await _persist_user(session, current_tenant, user_block)

    # НОВЫЙ ПОЛЬЗОВАТЕЛЬ - требуется регистрация
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not registered. Please complete registration first.",
            headers={"X-Registration-Required": "true"}
        )

    token_payload = {
        "sub": str(user.id),
        "role": user.role,
        "telegram_id": user.telegram_id,
        "tenant_id": user.tenant_id,
    }

    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)

    user_response = UserPayload(
        id=user.id,
        role=user.role,
        display_name=user.display_name,
        username=user.username,
        telegram_id=user.telegram_id,
        last_login_at=user.last_login_at,
    )

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response,
    )


@router.post("/refresh", response_model=TokenPairResponse)
@rate_limit("10/minute")  # Allow more refreshes than login attempts (disabled in dev mode)
async def refresh(
    request: Request,
    payload: RefreshRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
    try:
        token_data = decode_token(payload.refresh_token, TokenType.REFRESH)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    user_id = token_data.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await crud.get_user(session, int(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    reference_payload = {
        "sub": str(user.id),
        "role": user.role,
        "telegram_id": user.telegram_id,
        "tenant_id": user.tenant_id,
    }

    access_token = create_access_token(reference_payload)
    refresh_token = create_refresh_token(reference_payload)

    user_response = UserPayload(
        id=user.id,
        role=user.role,
        display_name=user.display_name,
        username=user.username,
        telegram_id=user.telegram_id,
        last_login_at=user.last_login_at,
    )

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response,
    )


@router.post("/switch-tenant", response_model=TokenPairResponse)
@rate_limit("10/minute")  # Prevent abuse of tenant switching (disabled in dev mode)
async def switch_tenant(
    request: Request,
    payload: SwitchTenantRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> TokenPairResponse:
    """
    Switch tenant context for super-admins.
    This is a critical security endpoint - only super-admins can use it.
    """
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super-admins can switch tenant context"
        )
    
    target_tenant_id = payload.tenant_id
    target_tenant = None
    
    # If switching to a specific tenant, validate it exists and is active
    if target_tenant_id is not None:
        target_tenant = await session.get(Tenant, target_tenant_id)
        if not target_tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant {target_tenant_id} not found"
            )
        if not target_tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant {target_tenant_id} is inactive"
            )
    
    # Create new tokens with the target tenant context
    token_payload = {
        "sub": str(current_user.id),
        "role": current_user.role,
        "telegram_id": current_user.telegram_id,
        "tenant_id": target_tenant_id,  # This is the key change
    }
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    
    user_response = UserPayload(
        id=current_user.id,
        role=current_user.role,
        display_name=current_user.display_name,
        username=current_user.username,
        telegram_id=current_user.telegram_id,
        last_login_at=current_user.last_login_at,
    )
    
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response,
    )