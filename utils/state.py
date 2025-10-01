from __future__ import annotations

from datetime import datetime
from typing import Optional


_bot_started_at: Optional[datetime] = None


def set_bot_started_at(value: datetime) -> None:
    global _bot_started_at
    _bot_started_at = value


def get_bot_started_at() -> Optional[datetime]:
    return _bot_started_at
