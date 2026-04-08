from __future__ import annotations

from dataclasses import dataclass, field

from notifications.domain.entities import EffectivePreferences
from notifications.domain.enums import CategoryKey, EventType
from notifications.domain.preferences import is_category_enabled


@dataclass(frozen=True)
class EligibilityContext:
    event_type: EventType
    category: CategoryKey
    recipient_has_contact: bool = True
    learner_notifications_enabled: bool = True
    preferences: EffectivePreferences = field(default_factory=EffectivePreferences)
    package_status: str | None = None
    lesson_status: str | None = None
    has_homework: bool | None = None


@dataclass(frozen=True)
class EligibilityResult:
    eligible: bool
    reason: str = "eligible"
    warnings: tuple[str, ...] = ()


def evaluate_eligibility(context: EligibilityContext) -> EligibilityResult:
    if not context.recipient_has_contact:
        return EligibilityResult(False, "missing_contact")
    if not context.learner_notifications_enabled:
        return EligibilityResult(False, "learner_notifications_disabled")
    if not context.preferences.notifications_enabled:
        return EligibilityResult(False, "preferences_notifications_disabled")
    if not is_category_enabled(context.preferences, context.category):
        return EligibilityResult(False, "category_disabled")

    if context.event_type == EventType.LESSON:
        if context.package_status and context.package_status != "active":
            return EligibilityResult(False, "package_not_active")
        if context.lesson_status and context.lesson_status not in {"scheduled", "rescheduled"}:
            return EligibilityResult(False, "lesson_not_schedulable")
        if context.category == CategoryKey.HOMEWORK and context.has_homework is False:
            return EligibilityResult(False, "lesson_has_no_homework")

    if context.event_type == EventType.PACKAGE:
        if context.package_status and context.package_status != "active":
            return EligibilityResult(False, "package_not_active")

    warnings: list[str] = []
    if context.category == CategoryKey.HOMEWORK and context.has_homework is None:
        warnings.append("homework_inherited")
    return EligibilityResult(True, warnings=tuple(warnings))
