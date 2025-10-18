from __future__ import annotations

import asyncio
import sys
import types
from datetime import datetime, timezone

import pytest

from api import metrics_updater
from api.dependencies import CurrentTenant
from database import crud
from tests import factories


class DummyGauge:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class DummyTask(asyncio.Task):
    pass


class DummySessionCtx:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_update_gauge_metrics(monkeypatch, db_session, current_tenant: CurrentTenant):
    learner = await factories.create_learner(db_session)
    package = await crud.create_lesson_package(
        db_session,
        current_tenant,
        learner=learner,
        title="Active",
        status="active",
        timezone_name="Europe/Moscow",
    )
    await db_session.flush()
    await crud.create_lesson(
        db_session,
        current_tenant,
        package,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
    )
    await db_session.flush()

    gauges_module = types.SimpleNamespace(
        active_packages_gauge=DummyGauge(),
        scheduled_lessons_gauge=DummyGauge(),
        learners_gauge=DummyGauge(),
    )
    monkeypatch.setitem(sys.modules, "api.prometheus_metrics", gauges_module)
    monkeypatch.setattr(metrics_updater, "async_session", lambda: DummySessionCtx(db_session))

    await metrics_updater.update_gauge_metrics()

    assert gauges_module.active_packages_gauge.value == 1
    assert gauges_module.scheduled_lessons_gauge.value == 1
    assert gauges_module.learners_gauge.value == 1


@pytest.mark.asyncio
async def test_update_gauge_metrics_without_prometheus(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "api.prometheus_metrics":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    await metrics_updater.update_gauge_metrics()


@pytest.mark.asyncio
async def test_lifespan_with_metrics(monkeypatch):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def fake_metrics_task():
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(metrics_updater, "metrics_updater_task", fake_metrics_task)

    async with metrics_updater.lifespan_with_metrics(None):
        await started.wait()

    await asyncio.sleep(0)  # allow cancellation propagation
    assert cancelled.is_set()