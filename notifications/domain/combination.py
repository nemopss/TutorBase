from __future__ import annotations

from collections import defaultdict

from notifications.domain.entities import CombinedNotificationCandidate, NotificationCandidate
from notifications.domain.enums import CategoryKey, Priority


LESSON_CONFIRMATION_HOMEWORK_COMBINATION = "lesson_confirmation_homework"


def dedupe_exact(candidates: list[NotificationCandidate]) -> list[NotificationCandidate]:
    seen: dict[tuple[object, ...], NotificationCandidate] = {}
    for candidate in candidates:
        seen.setdefault(candidate.exact_dedupe_key, candidate)
    return list(seen.values())


def combine_lesson_confirmation_and_homework(
    candidates: list[NotificationCandidate],
) -> list[NotificationCandidate | CombinedNotificationCandidate]:
    grouped: dict[tuple[object, ...], list[NotificationCandidate]] = defaultdict(list)
    for candidate in candidates:
        grouped[
            (
                candidate.learner_id,
                candidate.event_type,
                candidate.event_id,
                candidate.scheduled_for,
            )
        ].append(candidate)

    result: list[NotificationCandidate | CombinedNotificationCandidate] = []
    for group in grouped.values():
        confirmation = _first_by_category(group, CategoryKey.LESSON_CONFIRMATION)
        homework = _first_by_category(group, CategoryKey.HOMEWORK)
        if confirmation and homework:
            combined = CombinedNotificationCandidate(
                combination_key=LESSON_CONFIRMATION_HOMEWORK_COMBINATION,
                category=CategoryKey.LESSON_CONFIRMATION,
                event_type=confirmation.event_type,
                event_id=confirmation.event_id,
                learner_id=confirmation.learner_id,
                scheduled_for=confirmation.scheduled_for,
                priority=_max_priority((confirmation.priority, homework.priority)),
                components=(confirmation, homework),
            )
            result.append(combined)
            result.extend(candidate for candidate in group if candidate not in {confirmation, homework})
        else:
            result.extend(group)
    return result


def _first_by_category(
    candidates: list[NotificationCandidate],
    category: CategoryKey,
) -> NotificationCandidate | None:
    return next((candidate for candidate in candidates if candidate.category == category), None)


def _max_priority(priorities: tuple[Priority, ...]) -> Priority:
    order = {
        Priority.LOW: 0,
        Priority.NORMAL: 1,
        Priority.HIGH: 2,
    }
    return max(priorities, key=lambda priority: order[priority])
