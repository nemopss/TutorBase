from __future__ import annotations

from collections.abc import Iterable

from notifications.domain.entities import EffectivePreferences, NotificationPreference
from notifications.domain.enums import CategoryKey


def resolve_effective_preferences(
    global_preference: NotificationPreference | None,
    *,
    group_preferences: Iterable[NotificationPreference] = (),
    learner_preference: NotificationPreference | None = None,
    default_timezone: str = "Europe/Moscow",
) -> EffectivePreferences:
    effective = EffectivePreferences(timezone=default_timezone)
    for preference in _ordered_preferences(global_preference, group_preferences, learner_preference):
        effective = _apply_preference(effective, preference)
    return effective


def is_category_enabled(preferences: EffectivePreferences, category: CategoryKey) -> bool:
    return preferences.category_enabled.get(category, True)


def _ordered_preferences(
    global_preference: NotificationPreference | None,
    group_preferences: Iterable[NotificationPreference],
    learner_preference: NotificationPreference | None,
) -> list[NotificationPreference]:
    ordered = []
    if global_preference is not None:
        ordered.append(global_preference)
    ordered.extend(group_preferences)
    if learner_preference is not None:
        ordered.append(learner_preference)
    return ordered


def _apply_preference(
    effective: EffectivePreferences,
    preference: NotificationPreference,
) -> EffectivePreferences:
    category_enabled = dict(effective.category_enabled)
    category_enabled.update(preference.category_enabled)
    return EffectivePreferences(
        notifications_enabled=(
            effective.notifications_enabled
            if preference.notifications_enabled is None
            else preference.notifications_enabled
        ),
        quiet_hours=preference.quiet_hours or effective.quiet_hours,
        timezone=preference.timezone or effective.timezone,
        daily_cap=preference.daily_cap if preference.daily_cap is not None else effective.daily_cap,
        cap_mode=preference.cap_mode or effective.cap_mode,
        category_enabled=category_enabled,
    )
