import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from api.dependencies import get_current_user, require_roles
from api.security import create_access_token
from database import crud


@pytest.mark.asyncio
async def test_get_current_user_missing_credentials(db_session):
    with pytest.raises(HTTPException) as exc:
        await get_current_user(None, db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(db_session):
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="bad")
    with pytest.raises(HTTPException) as exc:
        await get_current_user(credentials, db_session)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_success(db_session):
    user = await crud.create_user(
        db_session,
        telegram_id=1,
        username="valid",
        display_name="Valid",
        role="viewer",
    )
    await db_session.flush()
    token = create_access_token({"sub": str(user.id), "role": user.role, "telegram_id": user.telegram_id})
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    result = await get_current_user(credentials, db_session)
    assert result.id == user.id


@pytest.mark.asyncio
async def test_require_roles_forbidden(db_session):
    checker = require_roles("admin")
    user = await crud.create_user(
        db_session,
        telegram_id=2,
        username="viewer",
        display_name="Viewer",
        role="viewer",
    )
    await db_session.flush()
    with pytest.raises(HTTPException) as exc:
        await checker(user)
    assert exc.value.status_code == 403
