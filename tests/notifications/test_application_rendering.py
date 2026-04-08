from datetime import datetime, timezone

import pytest

from notifications.application.dto import ClaimedNotificationInstance
from notifications.application.rendering import FallbackNotificationRenderer
from notifications.domain.enums import CategoryKey, EventType, Priority


def _claimed_instance(*, explanation=None) -> ClaimedNotificationInstance:
    return ClaimedNotificationInstance(
        instance_id=101,
        attempt_id=201,
        attempt_no=1,
        rule_id=1,
        category=CategoryKey.LESSON_CONFIRMATION,
        event_type=EventType.LESSON,
        event_id=617,
        recipient_type="learner",
        recipient_id=10,
        learner_id=10,
        effective_scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        priority=Priority.NORMAL,
        channel="telegram",
        explanation=explanation or {},
    )


@pytest.mark.asyncio
async def test_fallback_renderer_prefers_rendered_text_from_explanation():
    rendered = await FallbackNotificationRenderer().render(
        _claimed_instance(explanation={"rendered_text": "Привет, Вика!"})
    )

    assert rendered.text == "Привет, Вика!"
    assert rendered.parse_mode is None


@pytest.mark.asyncio
async def test_fallback_renderer_uses_safe_debug_text_without_explanation():
    rendered = await FallbackNotificationRenderer().render(_claimed_instance())

    assert rendered.text == "Notification #101: lesson_confirmation for lesson"
