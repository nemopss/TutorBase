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
    RegistrationResponse,
    StudentRegistrationRequest,
    SwitchTenantRequest,
    TokenPairResponse,
    TutorRegistrationRequest,
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
    
    logger.info(f"[{request_id}] Tutor registration attempt: telegram_id={telegram_id}, school={registration_data.school_name}")
    
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
    
    try:
        await session.commit()
        logger.info(f"[{request_id}] Tutor registration successful: user_id={user.id}, tenant_id={tenant.id}, school={tenant.name}")
    except Exception as e:
        await session.rollback()
        logger.error(f"[{request_id}] Tutor registration failed during commit: {e}")
        
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
    
    logger.info(f"[{request_id}] Student registration attempt: telegram_id={telegram_id}, invite_token_prefix={registration_data.invite_token[:8]}")
    
    # Validate invite token
    invite_token = await crud.get_invite_token_by_token(session, registration_data.invite_token)
    if not invite_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invite code"
        )
    
    if invite_token.is_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This invite code has already been used"
        )
    
    if invite_token.is_expired:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This invite code has expired"
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
        logger.info(f"[{request_id}] Creating new BotUser for chat_id={telegram_id}")
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
    
    # Create learner record with bot_user_id
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
    
    # Create user record
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
    
    # Mark invite token as used
    await crud.mark_invite_token_as_used(session, invite_token)
    
    try:
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"[{request_id}] Student registration failed during commit: {e}")
        
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
