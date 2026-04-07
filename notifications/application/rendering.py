from __future__ import annotations

from notifications.application.dto import ClaimedNotificationInstance, RenderedNotification


class FallbackNotificationRenderer:
    async def render(self, instance: ClaimedNotificationInstance) -> RenderedNotification:
        explanation = instance.explanation or {}
        text = (
            explanation.get("rendered_text")
            or explanation.get("message")
            or _fallback_text(instance)
        )
        return RenderedNotification(text=str(text), parse_mode=None)


def _fallback_text(instance: ClaimedNotificationInstance) -> str:
    return (
        f"Notification #{instance.instance_id}: "
        f"{instance.category.value} for {instance.event_type.value}"
    )
