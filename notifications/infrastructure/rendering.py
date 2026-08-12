from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from database.models import Learner, Lesson, LessonPackage, User
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from notifications.application.delivery import NotificationDeliveryError
from notifications.application.dto import ClaimedNotificationInstance, RenderedNotification
from notifications.domain.enums import CategoryKey, EventType
from notifications.domain.templates import (
    ALLOWED_TEMPLATE_VARIABLE_KEYS,
    TemplateRenderError,
    render_template_body,
)
from notifications.infrastructure.models import (
    NotificationInstance,
    NotificationInstanceComponent,
    NotificationRule,
)


class SqlAlchemyNotificationRenderer:
    def __init__(self, session: AsyncSession, *, tenant_id: int) -> None:
        self._session = session
        self._tenant_id = tenant_id

    async def render(self, claimed: ClaimedNotificationInstance) -> RenderedNotification:
        instance = await self._load_instance(claimed.instance_id)
        if instance is None:
            raise NotificationDeliveryError(
                f"Notification instance {claimed.instance_id} not found",
                error_code="notification_instance_not_found",
                retryable=False,
            )

        context = await self._render_context(instance)
        try:
            text = render_template_body(_message_body(instance), context)
        except TemplateRenderError as exc:
            raise NotificationDeliveryError(
                str(exc),
                error_code="template_render_error",
                retryable=False,
            ) from exc

        return RenderedNotification(
            text=text,
            parse_mode=None,
            reply_markup_snapshot=_reply_markup_snapshot(claimed),
        )

    async def _load_instance(self, instance_id: int) -> NotificationInstance | None:
        result = await self._session.execute(_instance_for_render_stmt(self._tenant_id, instance_id))
        return result.scalar_one_or_none()

    async def _render_context(self, instance: NotificationInstance) -> dict[str, object]:
        context = {key: "" for key in ALLOWED_TEMPLATE_VARIABLE_KEYS}
        context["custom_note"] = str(
            (instance.manual_overrides or {}).get("custom_note") or ""
        )
        if instance.event_type == EventType.LESSON.value and instance.event_id is not None:
            context.update(await self._lesson_context(instance.event_id))
        elif instance.event_type == EventType.PACKAGE.value and instance.event_id is not None:
            context.update(await self._package_context(instance.event_id))
        return context

    async def _lesson_context(self, lesson_id: int) -> dict[str, object]:
        result = await self._session.execute(_lesson_render_context_stmt(self._tenant_id, lesson_id))
        row = result.one_or_none()
        if row is None:
            return {}
        tz = _timezone(row.timezone)
        lesson_dt = _to_local(row.lesson_scheduled_at, tz)
        homework_due_at = _to_local(row.homework_due_at, tz) if row.homework_due_at else None
        return {
            "student_name": row.learner_name,
            "lesson_date": lesson_dt.strftime("%d.%m.%Y"),
            "lesson_time": lesson_dt.strftime("%H:%M"),
            "lesson_datetime": lesson_dt.strftime("%d.%m.%Y %H:%M"),
            "package_title": row.package_title,
            "teacher_name": getattr(row, "teacher_name", "") or "",
            "homework_due_at": homework_due_at.strftime("%d.%m.%Y %H:%M") if homework_due_at else "",
        }

    async def _package_context(self, package_id: int) -> dict[str, object]:
        result = await self._session.execute(_package_render_context_stmt(self._tenant_id, package_id))
        row = result.one_or_none()
        if row is None:
            return {}
        tz = _timezone(row.timezone)
        package_end = _to_local(row.package_end, tz) if row.package_end else None
        return {
            "student_name": row.learner_name,
            "package_title": row.package_title,
            "package_end": package_end.strftime("%d.%m.%Y") if package_end else "",
            "teacher_name": getattr(row, "teacher_name", "") or "",
        }


def _teacher_name_subquery(tenant_id: int):
    return (
        select(User.display_name)
        .where(
            User.tenant_id == tenant_id,
            User.role.in_(("teacher", "admin")),
        )
        .order_by(case((User.role == "teacher", 0), else_=1), User.id)
        .limit(1)
        .scalar_subquery()
    )


def _instance_for_render_stmt(tenant_id: int, instance_id: int):
    return (
        select(NotificationInstance)
        .options(
            joinedload(NotificationInstance.rule).joinedload(NotificationRule.template),
            selectinload(NotificationInstance.components)
            .joinedload(NotificationInstanceComponent.rule)
            .joinedload(NotificationRule.template),
        )
        .where(
            NotificationInstance.tenant_id == tenant_id,
            NotificationInstance.id == instance_id,
        )
    )


def _lesson_render_context_stmt(tenant_id: int, lesson_id: int):
    return (
        select(
            Lesson.scheduled_at.label("lesson_scheduled_at"),
            Lesson.homework_due_at,
            LessonPackage.title.label("package_title"),
            LessonPackage.timezone,
            Learner.display_name.label("learner_name"),
            _teacher_name_subquery(tenant_id).label("teacher_name"),
        )
        .join(LessonPackage, LessonPackage.id == Lesson.package_id)
        .join(Learner, Learner.id == LessonPackage.learner_id)
        .where(
            Lesson.tenant_id == tenant_id,
            Lesson.id == lesson_id,
        )
    )


def _package_render_context_stmt(tenant_id: int, package_id: int):
    return (
        select(
            LessonPackage.title.label("package_title"),
            LessonPackage.end_date.label("package_end"),
            LessonPackage.timezone,
            Learner.display_name.label("learner_name"),
            _teacher_name_subquery(tenant_id).label("teacher_name"),
        )
        .join(Learner, Learner.id == LessonPackage.learner_id)
        .where(
            LessonPackage.tenant_id == tenant_id,
            LessonPackage.id == package_id,
        )
    )


def _message_body(instance: NotificationInstance) -> str:
    override = _manual_message_override(instance)
    if override:
        return override

    if instance.combination_key:
        component_bodies = tuple(
            body
            for body in (
                _component_message_body(component.rule, index=index)
                for index, component in enumerate(instance.components)
            )
            if body
        )
        if component_bodies:
            return "\n\n".join(component_bodies)

    body = _rule_message_body(instance.rule)
    if body:
        return body

    explanation = instance.explanation or {}
    fallback = explanation.get("message") or explanation.get("rendered_text")
    if fallback:
        return str(fallback)

    raise NotificationDeliveryError(
        f"Notification instance {instance.id} has no message body",
        error_code="missing_message_body",
        retryable=False,
    )


def _rule_message_body(rule: NotificationRule | None) -> str | None:
    if rule is None:
        return None
    if rule.inline_template_body:
        return rule.inline_template_body
    if rule.template is not None:
        return rule.template.body
    return None


def _component_message_body(rule: NotificationRule | None, *, index: int) -> str | None:
    body = _rule_message_body(rule)
    if body is None or index == 0:
        return body
    return _strip_duplicate_greeting(body)


def _strip_duplicate_greeting(body: str) -> str:
    for prefix in ("Привет, {student_name}! ", "Привет, {student_name}!\n"):
        if body.startswith(prefix):
            return body.removeprefix(prefix)
    return body


def _manual_message_override(instance: NotificationInstance) -> str | None:
    overrides = instance.manual_overrides or {}
    for key in ("message_override", "body", "rendered_text"):
        value = overrides.get(key)
        if value:
            return str(value)
    return None


def _timezone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or "Europe/Moscow")
    except Exception:
        return ZoneInfo("Europe/Moscow")


def _to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def _reply_markup_snapshot(claimed: ClaimedNotificationInstance) -> dict | None:
    if claimed.event_type == EventType.LESSON and claimed.category in {
        CategoryKey.LESSON_CONFIRMATION,
        CategoryKey.LESSON_REMINDER,
    }:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "👍 Подтверждаю",
                        "callback_data": f"notif_confirm_lesson_{claimed.instance_id}",
                    },
                ],
                [
                    {
                        "text": "😔 Не смогу",
                        "callback_data": f"notif_decline_lesson_{claimed.instance_id}",
                    },
                ],
            ]
        }
    if claimed.event_type == EventType.PACKAGE and claimed.category == CategoryKey.PACKAGE_RENEWAL:
        return {
            "inline_keyboard": [
                [
                    {
                        "text": "✅ Всё хорошо, продолжаем",
                        "callback_data": f"notif_confirm_package_{claimed.instance_id}",
                    },
                ],
                [
                    {
                        "text": "🤔 Нужно обсудить",
                        "callback_data": f"notif_discuss_package_{claimed.instance_id}",
                    },
                ],
            ]
        }
    return None
