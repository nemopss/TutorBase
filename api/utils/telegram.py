"""Telegram-related utility functions."""
from __future__ import annotations

from typing import Dict

from fastapi import HTTPException, status

from api.security import InitDataVerificationError, verify_telegram_init_data
from config import config


def validate_telegram_user(init_data: str) -> Dict[str, object]:
    """Validate Telegram init data and return user block.
    
    Handles both DEV_MODE (for testing) and production validation.
    
    Args:
        init_data: Telegram init data string from request header
        
    Returns:
        User data dictionary with keys: id, first_name, last_name, username
        
    Raises:
        HTTPException: If validation fails
    """
    if not init_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram init data required"
        )
    
    # Handle dev mode or real Telegram validation
    if config.DEV_MODE and init_data == config.DEV_INIT_DATA:
        return {
            "id": config.DEV_TELEGRAM_ID,
            "first_name": config.DEV_DISPLAY_NAME,
            "username": config.DEV_USERNAME,
        }
    else:
        try:
            init_payload = verify_telegram_init_data(init_data, config.BOT_TOKEN)
            user_block = init_payload.get("user")
            
            if not isinstance(user_block, dict):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing user payload in Telegram data"
                )
            
            return user_block
            
        except InitDataVerificationError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Telegram init data"
            ) from exc


def build_display_name(user_data: Dict[str, object]) -> str:
    """Build display name from Telegram user data.
    
    Args:
        user_data: User data dictionary from Telegram
        
    Returns:
        Display name string (first_name + last_name or username or fallback)
    """
    first_name = user_data.get("first_name") or ""
    last_name = user_data.get("last_name") or ""
    username = user_data.get("username")
    
    if first_name or last_name:
        return f"{first_name} {last_name}".strip()
    elif username:
        return username
    
    # Fallback
    telegram_id = user_data.get("id")
    return f"tg:{telegram_id}" if telegram_id is not None else "Telegram User"
