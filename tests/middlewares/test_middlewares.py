from __future__ import annotations

import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Update, Message, User, Chat
from redis.exceptions import RedisError

from middlewares.db import DbSessionMiddleware
from middlewares.logging import LoggingMiddleware, update_id_var
from middlewares.rate_limit import RateLimitMiddleware
from middlewares.user_tracking import UserTrackingMiddleware
from database import crud


class DummySession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


class DummySessionContext:
    def __init__(self, session: DummySession):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_db_session_middleware_commit(monkeypatch):
    session = DummySession()
    middleware = DbSessionMiddleware()

    def fake_async_session():
        return DummySessionContext(session)

    monkeypatch.setattr("middlewares.db.async_session", fake_async_session)

    async def handler(event, data):
        assert data["session"] is session
        return "ok"

    result = await middleware(handler, SimpleNamespace(), {})
    assert result == "ok"
    assert session.commits == 1
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_db_session_middleware_rollback(monkeypatch):
    session = DummySession()
    middleware = DbSessionMiddleware()

    monkeypatch.setattr("middlewares.db.async_session", lambda: DummySessionContext(session))

    async def handler(event, data):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await middleware(handler, SimpleNamespace(), {})

    assert session.commits == 0
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_logging_middleware_sets_context():
    middleware = LoggingMiddleware()

    async def handler(event, data):
        assert update_id_var.get() == event.update_id
        return "done"

    event = SimpleNamespace(update_id=42)
    assert await middleware(handler, event, {}) == "done"


def _build_update(user_id: int = 1) -> Update:
    user = User(id=user_id, is_bot=False, first_name="User")
    chat = Chat(id=10, type="private")
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=chat,
        from_user=user,
        text="hello",
    )
    answer_mock = AsyncMock()
    object.__setattr__(message, "answer", answer_mock)
    update = Update(update_id=1, message=message)
    return update


class FakeRedis:
    def __init__(self):
        self.store: dict[str, int] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: int):
        self.store[key] = int(value)

    async def incr(self, key: str):
        self.store[key] = self.store.get(key, 0) + 1

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_rate_limit_allows_within_limits(monkeypatch):
    redis = FakeRedis()
    middleware = RateLimitMiddleware(max_requests=2, window_seconds=60)
    monkeypatch.setattr(middleware, "_get_redis", AsyncMock(return_value=redis))

    handler = AsyncMock(return_value="ok")
    update = _build_update()

    await middleware(handler, update, {})
    await middleware(handler, update, {})

    assert handler.await_count == 2
    assert update.message.answer.await_count == 0


@pytest.mark.asyncio
async def test_rate_limit_blocks_excess(monkeypatch):
    redis = FakeRedis()
    middleware = RateLimitMiddleware(max_requests=2, window_seconds=60)
    monkeypatch.setattr(middleware, "_get_redis", AsyncMock(return_value=redis))

    handler = AsyncMock()
    update = _build_update()

    await middleware(handler, update, {})
    await middleware(handler, update, {})
    await middleware(handler, update, {})  # exceeds limit

    assert handler.await_count == 2
    update.message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_rate_limit_fail_open_on_redis_error(monkeypatch):
    middleware = RateLimitMiddleware()

    async def exploding():
        raise RedisError("boom")

    monkeypatch.setattr(middleware, "_get_redis", exploding)
    handler = AsyncMock()
    update = _build_update()

    await middleware(handler, update, {})
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_rate_limit_close():
    redis = FakeRedis()
    middleware = RateLimitMiddleware()
    middleware._redis = redis
    await middleware.close()


@pytest.mark.asyncio
async def test_user_tracking_middleware(monkeypatch):
    middleware = UserTrackingMiddleware()
    session = DummySession()
    user = User(id=999, is_bot=False, first_name="Tracked")
    message = Message(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        from_user=user,
        text="hi",
    )
    update = Update(update_id=1, message=message)

    calls: list[tuple] = []

    async def fake_upsert(session_arg, user_arg):
        calls.append((session_arg, user_arg))

    monkeypatch.setattr(crud, "upsert_bot_user", fake_upsert)

    async def handler(event, data):
        return "ok"

    data = {"session": session, "event_from_user": user}
    assert await middleware(handler, update, data) == "ok"
    assert calls and calls[0][0] is session


@pytest.mark.asyncio
async def test_user_tracking_without_user(monkeypatch):
    middleware = UserTrackingMiddleware()
    session = DummySession()
    calls: list = []
    monkeypatch.setattr(crud, "upsert_bot_user", lambda *args, **kwargs: calls.append(args))

    async def handler(event, data):
        return "done"

    update = SimpleNamespace(event=None)
    assert await middleware(handler, update, {"session": session}) == "done"
    assert calls == []
