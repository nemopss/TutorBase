import pytest

from config import config
from notifications.domain.enums import NotificationSystemMode
from notifications.infrastructure.modes import (
    SqlAlchemyNotificationModeResolver,
    should_suppress_legacy_reminder_for_learner,
)


class FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def scalar_one_or_none(self):
        if not self._values:
            return None
        return self._values.pop(0)


class FakeSession:
    def __init__(self, values):
        self.values = list(values)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.values)


@pytest.mark.asyncio
async def test_mode_resolver_defaults_to_legacy_without_settings():
    mode = await SqlAlchemyNotificationModeResolver(
        FakeSession([]),
        tenant_id=1,
    ).effective_mode_for_learner(learner_id=10)

    assert mode == NotificationSystemMode.LEGACY


@pytest.mark.asyncio
async def test_mode_resolver_uses_learner_override_over_tenant_mode():
    mode = await SqlAlchemyNotificationModeResolver(
        FakeSession(["new"]),
        tenant_id=1,
    ).effective_mode_for_learner(learner_id=10)

    assert mode == NotificationSystemMode.NEW


@pytest.mark.asyncio
async def test_mode_resolver_uses_tenant_mode_when_learner_inherits():
    mode = await SqlAlchemyNotificationModeResolver(
        FakeSession(["inherit", "shadow"]),
        tenant_id=1,
    ).effective_mode_for_learner(learner_id=10)

    assert mode == NotificationSystemMode.SHADOW


@pytest.mark.asyncio
async def test_legacy_suppression_only_applies_in_new_mode(monkeypatch):
    monkeypatch.setattr(config, "NOTIFICATIONS_AUTOMATION_ENABLED", True)
    assert await should_suppress_legacy_reminder_for_learner(
        FakeSession(["new"]),
        tenant_id=1,
        learner_id=10,
    )


@pytest.mark.asyncio
async def test_legacy_is_not_suppressed_when_new_automation_is_disabled(monkeypatch):
    monkeypatch.setattr(config, "NOTIFICATIONS_AUTOMATION_ENABLED", False)

    assert not await should_suppress_legacy_reminder_for_learner(
        FakeSession(["new"]),
        tenant_id=1,
        learner_id=10,
    )
    assert not await should_suppress_legacy_reminder_for_learner(
        FakeSession(["shadow"]),
        tenant_id=1,
        learner_id=10,
    )
