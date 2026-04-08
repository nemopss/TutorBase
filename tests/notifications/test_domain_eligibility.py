from notifications.domain.eligibility import EligibilityContext, evaluate_eligibility
from notifications.domain.entities import EffectivePreferences
from notifications.domain.enums import CategoryKey, EventType


def test_eligibility_rejects_disabled_learner_notifications():
    result = evaluate_eligibility(
        EligibilityContext(
            event_type=EventType.LESSON,
            category=CategoryKey.LESSON_CONFIRMATION,
            learner_notifications_enabled=False,
        )
    )

    assert result.eligible is False
    assert result.reason == "learner_notifications_disabled"


def test_eligibility_rejects_homework_when_lesson_has_no_homework():
    result = evaluate_eligibility(
        EligibilityContext(
            event_type=EventType.LESSON,
            category=CategoryKey.HOMEWORK,
            package_status="active",
            lesson_status="scheduled",
            has_homework=False,
        )
    )

    assert result.eligible is False
    assert result.reason == "lesson_has_no_homework"


def test_eligibility_warns_when_homework_is_inherited():
    result = evaluate_eligibility(
        EligibilityContext(
            event_type=EventType.LESSON,
            category=CategoryKey.HOMEWORK,
            package_status="active",
            lesson_status="scheduled",
            has_homework=None,
        )
    )

    assert result.eligible is True
    assert result.warnings == ("homework_inherited",)


def test_eligibility_rejects_category_disabled_by_preferences():
    result = evaluate_eligibility(
        EligibilityContext(
            event_type=EventType.LESSON,
            category=CategoryKey.HOMEWORK,
            preferences=EffectivePreferences(category_enabled={CategoryKey.HOMEWORK: False}),
        )
    )

    assert result.eligible is False
    assert result.reason == "category_disabled"
