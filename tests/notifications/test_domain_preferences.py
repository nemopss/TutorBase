from datetime import time

from notifications.domain.entities import NotificationPreference, QuietHours
from notifications.domain.enums import CapMode, CategoryKey, PreferenceScope
from notifications.domain.preferences import is_category_enabled, resolve_effective_preferences


def test_learner_preferences_override_global_defaults():
    global_preference = NotificationPreference(
        scope_type=PreferenceScope.GLOBAL,
        daily_cap=3,
        timezone="Europe/Moscow",
        quiet_hours=QuietHours(start=time(21, 0), end=time(9, 0)),
        category_enabled={CategoryKey.HOMEWORK: True},
    )
    learner_preference = NotificationPreference(
        scope_type=PreferenceScope.LEARNER,
        scope_id=10,
        daily_cap=6,
        cap_mode=CapMode.WARN_ONLY,
        quiet_hours=QuietHours(start=time(20, 0), end=time(12, 0)),
        category_enabled={CategoryKey.HOMEWORK: False},
    )

    effective = resolve_effective_preferences(
        global_preference,
        learner_preference=learner_preference,
    )

    assert effective.daily_cap == 6
    assert effective.quiet_hours == learner_preference.quiet_hours
    assert effective.cap_mode == CapMode.WARN_ONLY
    assert is_category_enabled(effective, CategoryKey.HOMEWORK) is False
    assert is_category_enabled(effective, CategoryKey.LESSON_CONFIRMATION) is True
