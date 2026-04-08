from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

from notifications.domain.enums import (
    CapMode,
    CategoryKey,
    EventType,
    PreferenceScope,
    Priority,
    QuietHoursMode,
    TriggerType,
)


@dataclass(frozen=True)
class NotificationEvent:
    event_type: EventType
    event_id: int | str | None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str = "Europe/Moscow"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationTrigger:
    trigger_type: TriggerType
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QuietHours:
    start: time
    end: time
    mode: QuietHoursMode = QuietHoursMode.SHIFT


@dataclass(frozen=True)
class NotificationPreference:
    scope_type: PreferenceScope
    scope_id: int | str | None = None
    notifications_enabled: bool | None = None
    quiet_hours: QuietHours | None = None
    timezone: str | None = None
    daily_cap: int | None = None
    cap_mode: CapMode | None = None
    category_enabled: dict[CategoryKey, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class EffectivePreferences:
    notifications_enabled: bool = True
    quiet_hours: QuietHours | None = None
    timezone: str = "Europe/Moscow"
    daily_cap: int = 3
    cap_mode: CapMode = CapMode.WARN_ONLY
    category_enabled: dict[CategoryKey, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class NotificationCandidate:
    rule_id: int | str
    category: CategoryKey
    event_type: EventType
    event_id: int | str | None
    learner_id: int | str
    scheduled_for: datetime
    priority: Priority = Priority.NORMAL
    template_key: str | None = None
    message_fingerprint: str | None = None
    source_rule_ids: tuple[int | str, ...] = field(default_factory=tuple)

    @property
    def exact_dedupe_key(self) -> tuple[Any, ...]:
        return (
            self.learner_id,
            self.event_type,
            self.event_id,
            self.category,
            self.template_key,
            self.scheduled_for,
        )


@dataclass(frozen=True)
class CombinedNotificationCandidate:
    combination_key: str
    category: CategoryKey
    event_type: EventType
    event_id: int | str | None
    learner_id: int | str
    scheduled_for: datetime
    priority: Priority
    components: tuple[NotificationCandidate, ...]
