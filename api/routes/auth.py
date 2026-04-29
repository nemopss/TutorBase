from datetime import datetime, timezone
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.dependencies import (
    CurrentTenant,
    get_current_tenant,
    get_current_user,
    get_session,
    is_platform_admin,
)
from database.models import LegalAcceptance, Tenant, User
from api.schemas import (
    BrowserTokenResponse,
    RefreshRequest,
    RegistrationResponse,
    StudentRegistrationRequest,
    SwitchTenantRequest,
    TelegramLoginWidgetRequest,
    TokenPairResponse,
    TutorRegistrationRequest,
    UserPayload,
    WebAppLoginRequest,
)
from api.security import (
    InitDataVerificationError,
    TelegramLoginVerificationError,
    TokenType,
    TokenVerificationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_telegram_init_data,
    verify_telegram_login_widget,
)
from config import config
from database import crud
from services import billing_service, notification_bootstrap_service, tenant_access_service

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
BROWSER_REFRESH_COOKIE_PATH = "/api/v1/auth/browser"
_TOKEN_TENANT_UNSET = object()
OFFER_VERSION = "2026-04-29"
PRIVACY_VERSION = "2026-04-29"

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


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None
    return request.client.host if request.client else None


def _record_legal_acceptance(
    session: AsyncSession,
    request: Request,
    *,
    user: User,
    tenant_id: int | None,
) -> None:
    session.add(
        LegalAcceptance(
            user_id=user.id,
            tenant_id=tenant_id,
            role=user.role,
            offer_version=OFFER_VERSION,
            privacy_version=PRIVACY_VERSION,
            accepted_at=datetime.now(timezone.utc),
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    )


def _build_user_payload(user: User) -> UserPayload:
    return UserPayload(
        id=user.id,
        role=user.role,
        is_platform_admin=is_platform_admin(user),
        display_name=user.display_name,
        username=user.username,
        telegram_id=user.telegram_id,
        last_login_at=user.last_login_at,
    )


def _build_token_payload(
    user: User,
    *,
    tenant_id: int | None | object = _TOKEN_TENANT_UNSET,
) -> dict[str, object]:
    # `None` is a valid explicit global context for platform admins.
    resolved_tenant_id = user.tenant_id if tenant_id is _TOKEN_TENANT_UNSET else tenant_id
    return {
        "sub": str(user.id),
        "role": user.role,
        "is_platform_admin": is_platform_admin(user),
        "telegram_id": user.telegram_id,
        "tenant_id": resolved_tenant_id,
    }


def _set_browser_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=config.BROWSER_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=config.JWT_REFRESH_EXPIRES_SECONDS,
        httponly=True,
        secure=config.BROWSER_REFRESH_COOKIE_SECURE,
        samesite=config.BROWSER_REFRESH_COOKIE_SAMESITE,
        path=BROWSER_REFRESH_COOKIE_PATH,
    )


def _clear_browser_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=config.BROWSER_REFRESH_COOKIE_NAME,
        secure=config.BROWSER_REFRESH_COOKIE_SECURE,
        samesite=config.BROWSER_REFRESH_COOKIE_SAMESITE,
        path=BROWSER_REFRESH_COOKIE_PATH,
    )


def _browser_access_denied(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": code, "message": message},
    )


async def _persist_user(session: AsyncSession, current_tenant: CurrentTenant, user_data: Dict[str, object]):
    telegram_id = int(user_data["id"])
    username = user_data.get("username")
    display_name = _build_display_name(user_data)
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    now = datetime.now(timezone.utc)

    if user is None:
        # НОВЫЙ ПОЛЬЗОВАТЕЛЬ - требуется регистрация!
        # Возвращаем None, чтобы login endpoint мог обработать это
        return None
    else:
        user = await crud.update_user_login_metadata(
            session,
            user,
            username=username,
            display_name=display_name,
            role=None,
            last_login_at=now,
        )
    await session.flush()
    return user


async def _viewer_has_active_learner(session: AsyncSession, user: User) -> bool:
    """Return whether a viewer user is currently linked to a learner."""
    if user.role != "viewer":
        return True
    if user.tenant_id is None or user.telegram_id is None:
        return False

    bot_user = await crud.get_bot_user_by_chat_id(session, int(user.telegram_id))
    if not bot_user:
        return False

    learner = await crud.get_learner_by_bot_user(
        session,
        CurrentTenant(tenant_id=user.tenant_id, is_super_admin=False),
        bot_user.id,
    )
    return learner is not None


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

    if user.role == "viewer" and not await _viewer_has_active_learner(session, user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student account is not linked. Please complete registration first.",
            headers={"X-Registration-Required": "true"}
        )

    token_payload = _build_token_payload(user)

    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)

    user_response = _build_user_payload(user)

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

    reference_payload = _build_token_payload(user)

    access_token = create_access_token(reference_payload)
    refresh_token = create_refresh_token(reference_payload)

    user_response = _build_user_payload(user)

    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response,
    )


@router.post("/browser/telegram", response_model=BrowserTokenResponse)
@rate_limit("5/minute")
async def browser_telegram_login(
    request: Request,
    payload: TelegramLoginWidgetRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> BrowserTokenResponse:
    try:
        telegram_user = verify_telegram_login_widget(
            payload.model_dump(),
            config.BOT_TOKEN,
            config.TELEGRAM_AUTH_MAX_AGE_SECONDS,
        )
    except TelegramLoginVerificationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    telegram_id = int(telegram_user["id"])
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    if user is None:
        raise _browser_access_denied(
            "USER_NOT_REGISTERED",
            "User is not registered. Open the Telegram Mini App to complete registration first.",
        )

    if user.role != "teacher" and not is_platform_admin(user):
        raise _browser_access_denied(
            "BROWSER_ACCESS_NOT_ALLOWED",
            "Browser access is currently available only for teachers and admins.",
        )

    user = await crud.update_user_login_metadata(
        session,
        user,
        username=telegram_user.get("username"),
        display_name=_build_display_name(telegram_user),
        role=None,
        last_login_at=datetime.now(timezone.utc),
    )
    await session.flush()

    token_payload = _build_token_payload(user)
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    _set_browser_refresh_cookie(response, refresh_token)

    return BrowserTokenResponse(
        access_token=access_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=_build_user_payload(user),
    )


@router.post("/browser/refresh", response_model=BrowserTokenResponse)
@rate_limit("10/minute")
async def browser_refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> BrowserTokenResponse:
    refresh_token = request.cookies.get(config.BROWSER_REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    try:
        token_data = decode_token(refresh_token, TokenType.REFRESH)
    except TokenVerificationError as exc:
        _clear_browser_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    user_id = token_data.get("sub")
    if user_id is None:
        _clear_browser_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await crud.get_user(session, int(user_id))
    if not user:
        _clear_browser_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.role != "teacher" and not is_platform_admin(user):
        _clear_browser_refresh_cookie(response)
        raise _browser_access_denied(
            "BROWSER_ACCESS_NOT_ALLOWED",
            "Browser access is currently available only for teachers and admins.",
        )

    token_payload = _build_token_payload(user)
    access_token = create_access_token(token_payload)
    next_refresh_token = create_refresh_token(token_payload)
    _set_browser_refresh_cookie(response, next_refresh_token)

    return BrowserTokenResponse(
        access_token=access_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=_build_user_payload(user),
    )


@router.post("/browser/logout", status_code=status.HTTP_204_NO_CONTENT)
async def browser_logout(response: Response) -> None:
    _clear_browser_refresh_cookie(response)


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
    if not is_platform_admin(current_user):
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
    token_payload = _build_token_payload(current_user, tenant_id=target_tenant_id)
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    
    user_response = _build_user_payload(current_user)
    
    return TokenPairResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response,
    )


@router.post("/register-tutor", response_model=RegistrationResponse)
@rate_limit("3/minute")  # Prevent registration abuse
async def register_tutor(
    request: Request,
    registration_data: TutorRegistrationRequest,
    session: AsyncSession = Depends(get_session),
) -> RegistrationResponse:
    """Register a new tutor and create their tenant (school)."""
    from api.utils import validate_telegram_user, build_display_name
    import logging
    import uuid
    
    logger = logging.getLogger(__name__)
    request_id = str(uuid.uuid4())[:8]  # Short ID for logs
    
    # Validate Telegram init data
    init_data = request.headers.get("X-Telegram-Init-Data")
    user_block = validate_telegram_user(init_data)
    
    telegram_id = int(user_block["id"])
    username = user_block.get("username")
    telegram_display_name = build_display_name(user_block)
    
    logger.info(f"[{request_id}] Tutor registration attempt")
    
    # Generate slug for tenant
    import re
    slug = re.sub(r'[^a-zA-Z0-9-]', '-', registration_data.school_name.lower()).strip('-')
    slug = re.sub(r'-+', '-', slug)  # Remove multiple consecutive dashes
    
    # Ensure slug is unique by appending counter if needed
    from sqlalchemy import select
    base_slug = slug
    counter = 1
    MAX_SLUG_ATTEMPTS = 100
    
    while counter < MAX_SLUG_ATTEMPTS:
        existing_slug = await session.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        if not existing_slug.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1
    else:
        logger.error(f"[{request_id}] Failed to generate unique slug after {MAX_SLUG_ATTEMPTS} attempts")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate unique school identifier. Please try a different school name."
        )
    
    # Create tenant and user - let database constraints handle uniqueness
    tenant = Tenant(
        name=registration_data.school_name,
        slug=slug,
        contact_email=registration_data.contact_email,
        is_active=True,
    )
    session.add(tenant)
    await session.flush()  # Get tenant.id
    await tenant_access_service.create_default_free_access(session, tenant.id)
    await billing_service.ensure_subscription(
        session,
        tenant.id,
        notes="Created during tutor registration",
    )
    await notification_bootstrap_service.ensure_recommended_notification_rules(session, tenant.id)
    
    # Create user with teacher role
    display_name = registration_data.tutor_name or telegram_display_name
    
    user = User(
        telegram_id=telegram_id,
        username=username,
        display_name=display_name,
        role="teacher",
        tenant_id=tenant.id,
        last_login_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.flush()
    _record_legal_acceptance(session, request, user=user, tenant_id=tenant.id)
    
    try:
        await session.commit()
        logger.info(f"[{request_id}] Tutor registration successful: user_id={user.id}, tenant_id={tenant.id}")
    except Exception as e:
        await session.rollback()
        logger.error(f"[{request_id}] Tutor registration failed during commit: {type(e).__name__}")
        
        # Handle specific constraint violations
        from sqlalchemy.exc import IntegrityError
        if isinstance(e, IntegrityError):
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            
            # Check which constraint was violated
            if 'tenants_name_key' in error_msg or 'tenants.name' in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="School name already taken"
                )
            elif 'users_telegram_id_key' in error_msg or 'users.telegram_id' in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already registered"
                )
        
        # Generic error for other cases
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )
    
    # Create JWT tokens
    token_payload = _build_token_payload(user)
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    
    user_response = _build_user_payload(user)
    
    tenant_response = {
        "id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
    }
    
    return RegistrationResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response.model_dump(),
        tenant=tenant_response,
        message=f"Welcome! Your school '{tenant.name}' has been created successfully."
    )


@router.post("/register-student", response_model=RegistrationResponse)
@rate_limit("5/minute")  # Allow more attempts for students (they might mistype codes)
async def register_student(
    request: Request,
    registration_data: StudentRegistrationRequest,
    session: AsyncSession = Depends(get_session),
) -> RegistrationResponse:
    """Register a new student using an invite token."""
    from api.utils import validate_telegram_user, build_display_name
    import logging
    import uuid
    
    logger = logging.getLogger(__name__)
    request_id = str(uuid.uuid4())[:8]  # Short ID for logs
    
    # Validate Telegram init data
    init_data = request.headers.get("X-Telegram-Init-Data")
    user_block = validate_telegram_user(init_data)
    
    telegram_id = int(user_block["id"])
    username = user_block.get("username")
    telegram_display_name = build_display_name(user_block)
    
    logger.info(f"[{request_id}] Student registration attempt")
    
    # Atomically reserve the invite token for this transaction.
    invite_token = await crud.consume_invite_token_for_registration(session, registration_data.invite_token)
    if not invite_token:
        existing_token = await crud.get_invite_token_by_token(session, registration_data.invite_token)
        if existing_token:
            if existing_token.is_used:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This invite code has already been used"
                )
            if existing_token.is_expired:
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="This invite code has expired"
                )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code"
        )
    
    # Create bot_user and learner records
    from database.models import Learner, BotUser
    display_name = registration_data.student_name or telegram_display_name
    
    # Check for existing BotUser (upsert pattern)
    bot_user = await crud.get_bot_user_by_chat_id(session, telegram_id)
    
    if bot_user:
        # Update existing BotUser record
        logger.info(f"[{request_id}] Found existing BotUser: bot_user_id={bot_user.id}, updating metadata")
        bot_user.username = username
        bot_user.first_name = display_name.split()[0] if display_name else "User"
        bot_user.last_name = " ".join(display_name.split()[1:]) if len(display_name.split()) > 1 else ""
        bot_user.language_code = user_block.get("language_code", "en")
        bot_user.updated_at = datetime.now(timezone.utc)
        bot_user.last_seen_at = datetime.now(timezone.utc)
        session.add(bot_user)
    else:
        # Create new BotUser record
        logger.info(f"[{request_id}] Creating new BotUser")
        bot_user = BotUser(
            chat_id=telegram_id,
            username=username,
            first_name=display_name.split()[0] if display_name else "User",
            last_name=" ".join(display_name.split()[1:]) if len(display_name.split()) > 1 else "",
            language_code=user_block.get("language_code", "en"),
            is_bot=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        session.add(bot_user)
    
    await session.flush()  # Get bot_user.id

    active_learner = await crud.get_learner_by_bot_user(
        session,
        CurrentTenant(tenant_id=invite_token.tenant_id, is_super_admin=False),
        bot_user.id,
    )
    if active_learner:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Already registered as a student in this school"
        )
    
    if invite_token.learner_id:
        learner = invite_token.learner
        if not learner or learner.tenant_id != invite_token.tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invite learner not found"
            )
        if learner.bot_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Learner is already linked to a Telegram account"
            )
        learner.bot_user_id = bot_user.id
        learner.bot_user = bot_user
        learner.notifications_enabled = True
        session.add(learner)
        await session.flush()
    else:
        # Legacy tenant-level invite: create a new learner record.
        learner = Learner(
            tenant_id=invite_token.tenant_id,
            bot_user_id=bot_user.id,
            display_name=display_name,
            notes=f"Registered via invite on {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            notifications_enabled=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(learner)
        await session.flush()  # Get learner.id
    
    # Create or relink user record. A reset/unlink keeps the User row for audit
    # history, so re-registration must reuse it instead of violating telegram_id.
    user = await crud.get_user_by_telegram_id(session, telegram_id)
    if user:
        from utils.cache import invalidate_cache

        if user.role != "viewer":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already registered"
            )
        user.username = username
        user.display_name = display_name
        user.role = "viewer"
        user.tenant_id = invite_token.tenant_id
        user.last_login_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        session.add(user)
        await invalidate_cache("users:_get_user_cached:*")
    else:
        user = User(
            telegram_id=telegram_id,
            username=username,
            display_name=display_name,
            role="viewer",
            tenant_id=invite_token.tenant_id,
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)
    await session.flush()

    await crud.create_learner_account_link(
        session,
        tenant_id=invite_token.tenant_id,
        learner_id=learner.id,
        bot_user_id=bot_user.id,
        user_id=user.id,
        telegram_id=telegram_id,
    )
    _record_legal_acceptance(session, request, user=user, tenant_id=invite_token.tenant_id)
    
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"[{request_id}] Student registration failed during commit: {type(e).__name__}")
        
        # Handle specific constraint violations
        from sqlalchemy.exc import IntegrityError
        if isinstance(e, IntegrityError):
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            
            # Check which constraint was violated
            if 'users_telegram_id_key' in error_msg or 'users.telegram_id' in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already registered"
                )
            elif 'bot_users_chat_id_key' in error_msg or 'bot_users.chat_id' in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User already registered"
                )
            elif 'learners_bot_user_id_key' in error_msg or 'learners.bot_user_id' in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Already registered as a student in this school"
                )
        
        # Generic error for other cases
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )
    
    # Create JWT tokens
    token_payload = _build_token_payload(user)
    
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    
    user_response = _build_user_payload(user)
    
    tenant_response = {
        "id": invite_token.tenant.id,
        "name": invite_token.tenant.name,
        "slug": invite_token.tenant.slug,
    }
    
    logger.info(f"[{request_id}] Student registration successful: user_id={user.id}, tenant_id={invite_token.tenant_id}, learner_id={learner.id}")
    
    return RegistrationResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=config.JWT_ACCESS_EXPIRES_SECONDS,
        user=user_response.model_dump(),
        tenant=tenant_response,
        message=f"Welcome to {invite_token.tenant.name}! You've successfully joined as a student."
    )
