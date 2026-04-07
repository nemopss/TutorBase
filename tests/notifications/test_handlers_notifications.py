import pytest

from handlers.notifications import _parse_instance_id, _tenant_id_for_instance


class FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class FakeSession:
    def __init__(self, value):
        self.value = value
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return FakeScalarResult(self.value)


def test_parse_instance_id_accepts_known_notification_prefix():
    assert _parse_instance_id("notif_confirm_lesson_101", prefix="notif_confirm_lesson_") == 101
    assert _parse_instance_id("bad_101", prefix="notif_confirm_lesson_") is None
    assert _parse_instance_id("notif_confirm_lesson_bad", prefix="notif_confirm_lesson_") is None


@pytest.mark.asyncio
async def test_tenant_id_for_instance_reads_tenant_from_notification_instance():
    session = FakeSession(1)

    tenant_id = await _tenant_id_for_instance(session, 101)

    assert tenant_id == 1
    assert session.statements
