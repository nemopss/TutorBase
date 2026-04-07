from datetime import datetime, timezone

from notifications.domain.combination import (
    LESSON_CONFIRMATION_HOMEWORK_COMBINATION,
    combine_lesson_confirmation_and_homework,
    dedupe_exact,
)
from notifications.domain.entities import CombinedNotificationCandidate, NotificationCandidate
from notifications.domain.enums import CategoryKey, EventType, Priority


def _candidate(
    rule_id: int,
    category: CategoryKey,
    *,
    template_key: str | None = None,
    event_id: int = 617,
) -> NotificationCandidate:
    return NotificationCandidate(
        rule_id=rule_id,
        category=category,
        event_type=EventType.LESSON,
        event_id=event_id,
        learner_id=10,
        scheduled_for=datetime(2026, 4, 7, 7, 0, tzinfo=timezone.utc),
        priority=Priority.NORMAL,
        template_key=template_key,
    )


def test_exact_dedupe_keeps_single_candidate_for_same_semantic_key():
    first = _candidate(1, CategoryKey.HOMEWORK, template_key="homework_default")
    duplicate = _candidate(2, CategoryKey.HOMEWORK, template_key="homework_default")
    different = _candidate(3, CategoryKey.HOMEWORK, template_key="custom_homework")

    result = dedupe_exact([first, duplicate, different])

    assert result == [first, different]


def test_combines_lesson_confirmation_and_homework_for_same_lesson_and_time():
    confirmation = _candidate(1, CategoryKey.LESSON_CONFIRMATION)
    homework = _candidate(2, CategoryKey.HOMEWORK)

    result = combine_lesson_confirmation_and_homework([confirmation, homework])

    assert len(result) == 1
    combined = result[0]
    assert isinstance(combined, CombinedNotificationCandidate)
    assert combined.combination_key == LESSON_CONFIRMATION_HOMEWORK_COMBINATION
    assert combined.components == (confirmation, homework)


def test_combination_does_not_merge_different_lessons():
    confirmation = _candidate(1, CategoryKey.LESSON_CONFIRMATION, event_id=617)
    homework = _candidate(2, CategoryKey.HOMEWORK, event_id=581)

    result = combine_lesson_confirmation_and_homework([confirmation, homework])

    assert result == [confirmation, homework]
