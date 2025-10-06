from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_session
from api.schemas import (
    RefreshRequest,
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


def _build_display_name(user_payload: dict[str, object]) -> str:
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


async def _persist_user(session: AsyncSession, user_data: dict[str, object]):
    telegram_id = int(user_data["id"])
    username = user_data.get("username")
    display_name = _build_display_name(user_data)

    user = await crud.get_user_by_telegram_id(session, telegram_id)
    now = datetime.now(timezone.utc)

    if user is None:
        user = await crud.create_user(
            session,
            telegram_id=telegram_id,
            username=username,
            display_name=display_name,
            role="teacher",
        )
    else:
        user = await crud.update_user_login_metadata(
            session,
            user,
            username=username,
            display_name=display_name,
            last_login_at=now,
        )
    return user


@router.post("/login", response_model=TokenPairResponse)
async def login(
    payload: WebAppLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenPairResponse:
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

    user = await _persist_user(session, user_block)
    await session.commit()

    token_payload = {
        "sub": str(user.id),
        "role": user.role,
        "telegram_id": user.telegram_id,
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
async def refresh(
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
